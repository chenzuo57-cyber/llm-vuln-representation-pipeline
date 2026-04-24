// Joern CLI script — dump DFG-like value-flow facts per wrapped function.
// Strategy (fast, scalable): serialize assignment and argument value flows
// from Joern AST/CALL nodes (no expensive all-path dataflow expansion).
//
// Run:
//   export JOERN_SNIPPET_DIR=/abs/path/to/snippet_dir
//   export JOERN_DFG_OUT=/abs/path/to/dfg_out
//   export JOERN_DFG_MAX_FLOWS=800   # optional cap per method
//   joern --script scripts/representations/joern_dump_dfg.sc

import _root_.io.shiftleft.semanticcpg.language.*

@main def dumpDfgMain(): Unit = {
  val inDir = Option(System.getenv("JOERN_SNIPPET_DIR")).getOrElse(
    throw new RuntimeException("Set JOERN_SNIPPET_DIR to the directory containing joern_*.c files")
  )
  val outDir = Option(System.getenv("JOERN_DFG_OUT")).getOrElse(
    throw new RuntimeException("Set JOERN_DFG_OUT to a directory for per-method .dfg.txt files")
  )
  java.nio.file.Files.createDirectories(java.nio.file.Path.of(outDir))

  importCode(inDir)

  def clean(s: String): String = s.replace("\n", "\\n").replace("\t", " ").trim
  def stripComments(s: String): String = {
    s.replaceAll("(?s)/\\*.*?\\*/", " ").replaceAll("(?m)//.*$", " ")
  }
  def textFallbackFlows(code: String): List[String] = {
    val cleaned = stripComments(code)
    val assignR = """\b([A-Za-z_]\w*)\s*=\s*([^;]+);""".r
    val callR = """\b([A-Za-z_]\w*)\s*\(([^)]*)\)\s*;""".r
    val condR = """\b(if|while|for)\s*\(([^)]*)\)""".r
    val retR = """\breturn\s+([^;]+);""".r
    val edges = scala.collection.mutable.ArrayBuffer.empty[String]

    assignR.findAllMatchIn(cleaned).foreach { m =>
      val lhs = clean(m.group(1))
      val rhs = clean(m.group(2))
      if (lhs.nonEmpty && rhs.nonEmpty) edges += s"DEF_USE\t$rhs\t$lhs"
    }
    callR.findAllMatchIn(cleaned).foreach { m =>
      val fn = clean(m.group(1))
      val args = Option(m.group(2)).getOrElse("")
      val dst = s"$fn(...)"
      args.split(",").map(_.trim).filter(_.nonEmpty).foreach { a =>
        val src = clean(a)
        if (src.nonEmpty) edges += s"ARG_FLOW\t$src\t$dst"
      }
    }
    condR.findAllMatchIn(cleaned).foreach { m =>
      val src = clean(m.group(2))
      val dst = s"COND_${clean(m.group(1))}"
      if (src.nonEmpty) edges += s"COND_FLOW\t$src\t$dst"
    }
    retR.findAllMatchIn(cleaned).foreach { m =>
      val src = clean(m.group(1))
      if (src.nonEmpty) edges += s"RET_FLOW\t$src\treturn"
    }
    edges.toList
  }
  def nonMetaMethodsForFile(fileName: String): List[nodes.Method] = {
    cpg.method
      .filter(mm => mm.filename == fileName && mm.name != "<global>" && !mm.name.startsWith("joern_"))
      .l
  }
  def selectSourceMethods(fileName: String, wrapper: nodes.Method): List[nodes.Method] = {
    val all = nonMetaMethodsForFile(fileName)
    if (all.isEmpty) return List(wrapper)

    val priority = all.filter { mm =>
      mm.name.matches("(?i).*(bad|good|goodG2B|goodB2G|CWE\\d+).*")
    }
    val chosen = if (priority.nonEmpty) priority else all
    // Keep the most informative methods when files are large.
    chosen.sortBy(mm => -Option(mm.code).map(_.length).getOrElse(0)).take(12)
  }

  val methods = cpg.method.name("joern_.*").l
  methods.foreach { m =>
    val name = m.name
    val edgeLines = scala.collection.mutable.ArrayBuffer.empty[String]
    val sourceMethods = selectSourceMethods(m.filename, m)

    sourceMethods.foreach { sm =>
      // 1) Definition-style flows: RHS -> LHS for assignments
      val assigns = sm.ast.isCall.name("<operator>.assignment").l
      assigns.foreach { a =>
        val lhs = clean(a.argument(1).code)
        val rhs = clean(a.argument(2).code)
        if (lhs.nonEmpty && rhs.nonEmpty) {
          edgeLines += s"DEF_USE\t$rhs\t$lhs"
        }
      }

      // 2) Value-to-operation flows: each argument -> call expression
      val calls = sm.ast.isCall.l
      calls.foreach { c =>
        val dst = clean(c.code)
        if (dst.nonEmpty) {
          c.argument.code.l.foreach { argCode =>
            val src = clean(argCode)
            if (src.nonEmpty && src != dst) {
              edgeLines += s"ARG_FLOW\t$src\t$dst"
            }
          }
        }
      }

      // 3) Condition and return flows (helps Juliet where dataflow is sparse)
      sm.ast.isControlStructure.condition.code.l.foreach { cond =>
        val src = clean(cond)
        if (src.nonEmpty) {
          val dst = s"COND_${clean(sm.name)}"
          edgeLines += s"COND_FLOW\t$src\t$dst"
        }
      }
      sm.ast.isReturn.code.l.foreach { rc =>
        val src = clean(rc)
        if (src.nonEmpty) edgeLines += s"RET_FLOW\t$src\treturn"
      }
    }

    val methodLines = sourceMethods
      .map(sm => s"METHOD\t${clean(sm.signature)}")
      .distinct
    val fallbackEdges =
      if (edgeLines.isEmpty) {
        val codeBlob = sourceMethods.map(sm => Option(sm.code).getOrElse("")).mkString("\n")
        textFallbackFlows(codeBlob)
      } else Nil
    val text = (methodLines ++ edgeLines.toList.distinct ++ fallbackEdges.distinct).mkString("\n")
    val path = java.nio.file.Path.of(outDir, s"$name.dfg.txt")
    java.nio.file.Files.writeString(path, text, java.nio.charset.StandardCharsets.UTF_8)
  }

  println(s"Wrote ${methods.size} DFG dumps under $outDir")
}
