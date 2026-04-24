// Joern CLI script — dump CFG nodes and edges per wrapped function.
// Run:
//   export JOERN_SNIPPET_DIR=/abs/path/to/snippet_dir
//   export JOERN_CFG_OUT=/abs/path/to/cfg_out
//   joern --script scripts/representations/joern_dump_cfg.sc

@main def dumpCfgMain(): Unit = {
  val inDir = Option(System.getenv("JOERN_SNIPPET_DIR")).getOrElse(
    throw new RuntimeException("Set JOERN_SNIPPET_DIR to the directory containing joern_*.c files")
  )
  val outDir = Option(System.getenv("JOERN_CFG_OUT")).getOrElse(
    throw new RuntimeException("Set JOERN_CFG_OUT to a directory for per-method .cfg.txt files")
  )

  java.nio.file.Files.createDirectories(java.nio.file.Path.of(outDir))

  importCode(inDir)

  val methods = cpg.method.name("joern_.*").l
  methods.foreach { m =>
    val name = m.name
    val nodes = m.cfgNode.l.sortBy(_.order)
    val nodeLines = nodes.map { n =>
      val t = try n.getClass.getSimpleName catch case _: Throwable => "CfgNode"
      val id = n.id
      val ord = n.order
      val code = Option(n.code).map(_.replace("\n", "\\n")).getOrElse("")
      s"NODE\t$id\t$ord\t$t\t$code"
    }

    val edgeLines = nodes.flatMap { src =>
      src.cfgNext.l.map { dst =>
        val sc = Option(src.code).map(_.replace("\n", "\\n")).getOrElse("")
        val dc = Option(dst.code).map(_.replace("\n", "\\n")).getOrElse("")
        s"EDGE\t${src.id}\t${dst.id}\t$sc\t$dc"
      }
    }

    val text = (s"METHOD\t${Option(m.code).getOrElse("")}" +: (nodeLines ++ edgeLines)).mkString("\n")
    val path = java.nio.file.Path.of(outDir, s"$name.cfg.txt")
    java.nio.file.Files.writeString(path, text, java.nio.charset.StandardCharsets.UTF_8)
  }

  println(s"Wrote ${methods.size} CFG dumps under $outDir")
}
