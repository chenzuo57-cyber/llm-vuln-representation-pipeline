// Joern CLI script — produce sliced code text per wrapped function.
// Practical slice heuristic:
//   1) anchor on sensitive calls (sinks)
//   2) include enclosing control structures for those calls
//   3) include assignments and calls touching sink-related identifiers
// Result is a reduced plain-code view for LLM input.
//
// Run:
//   export JOERN_SNIPPET_DIR=/abs/path/to/snippet_dir
//   export JOERN_SLICE_OUT=/abs/path/to/slice_out
//   joern --script scripts/representations/joern_dump_slice.sc

import _root_.io.shiftleft.semanticcpg.language.*

@main def dumpSliceMain(): Unit = {
  val inDir = Option(System.getenv("JOERN_SNIPPET_DIR")).getOrElse(
    throw new RuntimeException("Set JOERN_SNIPPET_DIR to the directory containing joern_*.c files")
  )
  val outDir = Option(System.getenv("JOERN_SLICE_OUT")).getOrElse(
    throw new RuntimeException("Set JOERN_SLICE_OUT to a directory for per-method .slice.txt files")
  )

  java.nio.file.Files.createDirectories(java.nio.file.Path.of(outDir))
  importCode(inDir)

  def stripComments(s: String): String = {
    s.replaceAll("(?s)/\\*.*?\\*/", " ").replaceAll("(?m)//.*$", " ")
  }
  def clean(s: String): String = stripComments(s).replace("\n", " ").replace("\t", " ").replaceAll("\\s+", " ").trim
  def nonMetaMethodsForFile(fileName: String): List[nodes.Method] = {
    cpg.method
      .filter(mm => mm.filename == fileName && mm.name != "<global>" && !mm.name.startsWith("joern_"))
      .l
  }
  val sinkRegex = "(?i).*(strcpy|strcat|sprintf|vsprintf|gets|scanf|sscanf|fscanf|memcpy|memmove|system|popen|execv|execl|malloc|calloc|realloc|free|open|read|write|recv|send|copy_to_user|copy_from_user).*"

  val methods = cpg.method.name("joern_.*").l
  methods.foreach { m =>
    val selected = scala.collection.mutable.ArrayBuffer.empty[(Int, String)]
    val sourceMethods = nonMetaMethodsForFile(m.filename) match {
      case xs if xs.nonEmpty => xs
      case _                 => List(m)
    }

    val sinkCalls = sourceMethods.flatMap(sm => sm.ast.isCall.name(sinkRegex).l)
    val idSet = scala.collection.mutable.Set.empty[String]

    sinkCalls.foreach { s =>
      val sc = clean(s.code)
      if (sc.nonEmpty) selected += ((s.order, sc))

      // Collect identifiers appearing in sink call arguments
      s.argument.isIdentifier.code.l.foreach { c =>
        val v = clean(c)
        if (v.nonEmpty) idSet += v
      }

      // Include nearest enclosing control structures (guards/loops)
      s.inAstMinusLeaf.isControlStructure.code.l.take(5).foreach { c =>
        val cc = clean(c)
        if (cc.nonEmpty) selected += ((s.order - 1, cc))
      }
    }

    // Include data-related statements touching sink identifiers
    if (idSet.nonEmpty) {
      val vars = idSet.toSet

      sourceMethods.flatMap(sm => sm.ast.isCall.name("<operator>.assignment").l).foreach { a =>
        val lhs = clean(a.argument(1).code)
        val rhs = clean(a.argument(2).code)
        val touches = vars.contains(lhs) || vars.exists(v => rhs.contains(v))
        if (touches) {
          val ac = clean(a.code)
          if (ac.nonEmpty) selected += ((a.order, ac))
        }
      }

      sourceMethods.flatMap(sm => sm.ast.isCall.l).foreach { c =>
        val cc = clean(c.code)
        if (cc.nonEmpty && vars.exists(v => cc.contains(v))) {
          selected += ((c.order, cc))
        }
      }
    }

    // Fallback: if no sink anchors found, keep top control/call statements.
    if (selected.isEmpty) {
      sourceMethods.flatMap(sm => sm.ast.isControlStructure.code.l).take(20).foreach { c =>
        val cc = clean(c)
        if (cc.nonEmpty) selected += ((0, cc))
      }
      sourceMethods.flatMap(sm => sm.ast.isCall.code.l).take(40).foreach { c =>
        val cc = clean(c)
        if (cc.nonEmpty) selected += ((0, cc))
      }
    }

    val sliceLines = selected
      .sortBy(_._1)
      .map(_._2)
      .distinct

    // Last-resort fallback: full wrapped method code (ensures non-empty representation).
    val text =
      if (sliceLines.nonEmpty) sliceLines.mkString("\n")
      else clean(sourceMethods.map(sm => Option(sm.code).getOrElse("")).mkString("\n"))
    val path = java.nio.file.Path.of(outDir, s"${m.name}.slice.txt")
    java.nio.file.Files.writeString(path, text, java.nio.charset.StandardCharsets.UTF_8)
  }

  println(s"Wrote ${methods.size} slice dumps under $outDir")
}
