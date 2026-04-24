// Joern CLI script — dump ordered AST lines per wrapped function.
// Run:
//   export JOERN_SNIPPET_DIR=/abs/path/to/snippet_dir   # contains *.c from prepare_joern_snippet_dir.py
//   export JOERN_AST_OUT=/abs/path/to/ast_out
//   joern --script scripts/representations/joern_dump_ast.sc
//
// Requires joern-cli on PATH (same install used for CFG/DFG/CPG later).

@main def dumpAstMain(): Unit = {
  val inDir = Option(System.getenv("JOERN_SNIPPET_DIR")).getOrElse(
    throw new RuntimeException("Set JOERN_SNIPPET_DIR to the directory containing joern_*.c files")
  )
  val outDir = Option(System.getenv("JOERN_AST_OUT")).getOrElse(
    throw new RuntimeException("Set JOERN_AST_OUT to a directory for per-method .ast.txt files")
  )

  java.nio.file.Files.createDirectories(java.nio.file.Path.of(outDir))

  importCode(inDir)

  // Wrapped static functions are named `joern_<16 hex>` inside each TU.
  val methods = cpg.method.name("joern_.*").l
  methods.foreach { m =>
    val name = m.name
    val lines = m.ast.l.sortBy(_.order).map { n =>
      val kind =
        try n.getClass.getSimpleName
        catch case _: Throwable => "Ast"
      val code = Option(n.code).map(_.replace("\n", "\\n")).getOrElse("")
      s"$kind\t$code"
    }
    val text = (s"METHOD\t${Option(m.code).getOrElse("")}" +: lines).mkString("\n")
    val path = java.nio.file.Path.of(outDir, s"$name.ast.txt")
    java.nio.file.Files.writeString(path, text, java.nio.charset.StandardCharsets.UTF_8)
  }

  println(s"Wrote ${methods.size} AST dumps under $outDir")
}
