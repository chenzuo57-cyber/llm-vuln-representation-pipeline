// Joern CLI script — dump compact CPG text per wrapped function.
// Sections:
//   - Syntax (selected AST calls/control structures)
//   - Control flow (CFG edges)
//   - Data flow (assignment/call-arg flow facts)
//   - Potential sinks (selected dangerous call names)
//
// Run:
//   export JOERN_SNIPPET_DIR=/abs/path/to/snippet_dir
//   export JOERN_CPG_OUT=/abs/path/to/cpg_out
//   joern --script scripts/representations/joern_dump_cpg.sc

import _root_.io.shiftleft.semanticcpg.language.*

@main def dumpCpgMain(): Unit = {
  val inDir = Option(System.getenv("JOERN_SNIPPET_DIR")).getOrElse(
    throw new RuntimeException("Set JOERN_SNIPPET_DIR to the directory containing joern_*.c files")
  )
  val outDir = Option(System.getenv("JOERN_CPG_OUT")).getOrElse(
    throw new RuntimeException("Set JOERN_CPG_OUT to a directory for per-method .cpg.txt files")
  )

  java.nio.file.Files.createDirectories(java.nio.file.Path.of(outDir))
  importCode(inDir)

  def stripComments(s: String): String = {
    s.replaceAll("(?s)/\\*.*?\\*/", " ").replaceAll("(?m)//.*$", " ")
  }
  def clean(s: String): String = stripComments(s).replace("\n", "\\n").replace("\t", " ").replaceAll("\\s+", " ").trim
  def nonMetaMethodsForFile(fileName: String): List[nodes.Method] = {
    cpg.method
      .filter(mm => mm.filename == fileName && mm.name != "<global>" && !mm.name.startsWith("joern_"))
      .l
  }
  def textFallbackLines(code: String): (List[String], List[String], List[String], List[String]) = {
    val cleaned = stripComments(code)
    val ctrlR = """\b(if|for|while|switch)\s*\([^)]*\)""".r
    val callR = """\b([A-Za-z_]\w*)\s*\(([^)]*)\)\s*;""".r
    val assignR = """\b([A-Za-z_]\w*)\s*=\s*([^;]+);""".r
    val sinkR = """(?i).*\b(strcpy|strcat|sprintf|vsprintf|gets|scanf|sscanf|fscanf|memcpy|memmove|system|popen|execv|execl|malloc|calloc|realloc|free|open|read|write|recv|send)\b.*""".r

    val syntax = scala.collection.mutable.ArrayBuffer.empty[String]
    val control = scala.collection.mutable.ArrayBuffer.empty[String]
    val data = scala.collection.mutable.ArrayBuffer.empty[String]
    val sinks = scala.collection.mutable.ArrayBuffer.empty[String]

    ctrlR.findAllMatchIn(cleaned).take(80).foreach { m =>
      val c = clean(m.matched)
      if (c.nonEmpty) syntax += s"- CTRL $c"
    }
    callR.findAllMatchIn(cleaned).take(180).foreach { m =>
      val fn = clean(m.group(1))
      val args = clean(Option(m.group(2)).getOrElse(""))
      val dst = s"$fn(...)"
      if (fn.nonEmpty) syntax += s"- CALL $fn($args)"
      if (args.nonEmpty) {
        args.split(",").map(_.trim).filter(_.nonEmpty).foreach { a =>
          data += s"- ARG_FLOW ${clean(a)} -> $dst"
        }
      }
      val callText = clean(m.matched)
      if (callText.nonEmpty && sinkR.pattern.matcher(callText).matches()) sinks += s"- $callText"
    }
    assignR.findAllMatchIn(cleaned).take(220).foreach { m =>
      val lhs = clean(m.group(1))
      val rhs = clean(m.group(2))
      if (lhs.nonEmpty && rhs.nonEmpty) data += s"- DEF_USE $rhs -> $lhs"
    }

    (syntax.toList, control.toList, data.toList, sinks.toList)
  }

  val sinkRegex = "(?i).*(strcpy|strcat|sprintf|vsprintf|gets|scanf|sscanf|fscanf|memcpy|memmove|system|popen|execv|execl|malloc|calloc|realloc|free|open|read|write|recv|send).*"

  val methods = cpg.method.name("joern_.*").l
  methods.foreach { m =>
    val sourceMethods = nonMetaMethodsForFile(m.filename) match {
      case xs if xs.nonEmpty => xs
      case _                 => List(m)
    }
    val sourceBlob = sourceMethods.map(sm => Option(sm.code).getOrElse("")).mkString("\n")

    val syntaxLines = scala.collection.mutable.ArrayBuffer.empty[String]
    sourceMethods.foreach { sm =>
      sm.ast.isControlStructure.code.l.take(80).foreach { c =>
        val cc = clean(c)
        if (cc.nonEmpty) syntaxLines += s"- CTRL $cc"
      }
      sm.ast.isCall.code.l.take(160).foreach { c =>
        val cc = clean(c)
        if (cc.nonEmpty) syntaxLines += s"- CALL $cc"
      }
    }

    val controlLines = scala.collection.mutable.ArrayBuffer.empty[String]
    sourceMethods.foreach { sm =>
      val cfgNodes = sm.cfgNode.l.sortBy(_.order)
      cfgNodes.flatMap { src =>
        src.cfgNext.l.map(dst => (clean(Option(src.code).getOrElse("")), clean(Option(dst.code).getOrElse(""))))
      }.take(300).foreach { case (src, dst) =>
        if (src.nonEmpty || dst.nonEmpty) controlLines += s"- $src -> $dst"
      }
    }

    val dataLines = scala.collection.mutable.ArrayBuffer.empty[String]
    sourceMethods.foreach { sm =>
      sm.ast.isCall.name("<operator>.assignment").l.take(200).foreach { a =>
        val lhs = clean(a.argument(1).code)
        val rhs = clean(a.argument(2).code)
        if (lhs.nonEmpty && rhs.nonEmpty) dataLines += s"- DEF_USE $rhs -> $lhs"
      }
      sm.ast.isCall.l.take(300).foreach { c =>
        val dst = clean(c.code)
        if (dst.nonEmpty) {
          c.argument.code.l.foreach { ac =>
            val src = clean(ac)
            if (src.nonEmpty && src != dst) dataLines += s"- ARG_FLOW $src -> $dst"
          }
        }
      }
    }

    val sinkLines = scala.collection.mutable.ArrayBuffer.empty[String]
    sourceMethods.foreach { sm =>
      sm.ast.isCall.name(sinkRegex).code.l.distinct.take(80).foreach { c =>
        val cc = clean(c)
        if (cc.nonEmpty) sinkLines += s"- $cc"
      }
    }

    val (synFb, ctrlFb, dataFb, sinkFb) = textFallbackLines(sourceBlob)
    if (syntaxLines.isEmpty) syntaxLines ++= synFb
    if (controlLines.isEmpty) controlLines ++= ctrlFb
    if (dataLines.isEmpty) dataLines ++= dataFb
    if (sinkLines.isEmpty) sinkLines ++= sinkFb

    val syntaxOut = syntaxLines.toList.distinct
    val controlOut = controlLines.toList.distinct
    val dataOut = dataLines.toList.distinct
    val sinkOut = sinkLines.toList.distinct

    if (controlOut.isEmpty && syntaxOut.nonEmpty) {
      syntaxOut.sliding(2).take(200).foreach {
        case List(a, b) => controlLines += s"- $a -> $b"
        case _          =>
      }
    }

    val sections = List(
      "CPG:",
      "Syntax:",
      (if (syntaxOut.nonEmpty) syntaxOut else List("- <none>")),
      "Control flow:",
      (if (controlLines.nonEmpty) controlLines.toList.distinct else List("- <none>")),
      "Data flow:",
      (if (dataOut.nonEmpty) dataOut else List("- <none>")),
      "Potential sinks:",
      (if (sinkOut.nonEmpty) sinkOut else List("- <none>"))
    )

    val flat = sections.flatMap {
      case s: String => List(s)
      case xs: List[?] => xs.asInstanceOf[List[String]]
      case _ => Nil
    }

    val text = flat.mkString("\n")
    val path = java.nio.file.Path.of(outDir, s"${m.name}.cpg.txt")
    java.nio.file.Files.writeString(path, text, java.nio.charset.StandardCharsets.UTF_8)
  }

  println(s"Wrote ${methods.size} CPG dumps under $outDir")
}
