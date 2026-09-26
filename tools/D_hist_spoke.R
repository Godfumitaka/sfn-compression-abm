# D の図を読むための分布の図（2026-09-26 アストラさんの指示。封をしない記述の図。判定しない）
# 中心的過程（通過群 L）を通り、内の世界偽の率が 5% 以下の定義について、外の世界偽の率のヒストグラム。
# 内と外それぞれ主張 20 本以上（世界不明を除く）に絞る。版・NSIM・L（6 と 3）・物差しごと。
#   物差し：旧（①≧1／①=0）・新（話した）・副（話して開示）・新①（走行全体で決めた）・新②（後半 t>=870 の主張だけ）
#   表に列が無い（走査が数えていない版）物差しは描かない。
# 使い方  Rscript tools/D_hist_spoke.R <表のある場所> <出力の場所> <題の頭> <表の頭（defs_spoke か defs_spoke3）> <腕>…
a <- commandArgs(trailingOnly=TRUE)
IN <- a[1]; OUT <- a[2]; HEAD <- a[3]; PRE <- a[4]; arms <- a[5:length(a)]
lab_arm <- function(x) {
  v <- if (grepl("^v31v2", x)) "v2" else if (grepl("^v31x_extv2", x)) "v3取込+v3.1罰" else if (grepl("^v31x_profit", x)) "D-31取込+v3罰" else if (grepl("^v31x_none", x)) "足さない+v3罰" else if (grepl("^v31a", x)) "v3.1a" else if (grepl("^v31b", x)) "v3.1b" else if (grepl("^v3c", x)) "v3" else x
  n <- if (grepl("n95", x)) " 0.95" else if (grepl("n80", x)) " 0.8" else ""
  f <- regmatches(x, regexpr("(hide|f00|f025|f10)", x)); if (grepl("alpha1", x)) f <- paste0(f, " α=1")
  paste0(v, n, " ", f)
}
nlab <- sapply(arms, lab_arm)   # ★ 2026-09-26：f や組の違う腕を並べるので、版・NSIM・f を見出しに出す
TB <- lapply(arms, function(x) read.csv(file.path(IN, sprintf("%s_%s.csv", PRE, x))))
MS <- list(list(s="", lab="旧（①≧1／①=0）"), list(s="_spk", lab="新（話した）"), list(s="_fb", lab="副（話して開示）"),
           list(s="_all", lab="新①（走行全体）"), list(s="_late", lab="新②（後半だけ）"))
has <- function(t, s) all(paste0(c("rate_in","rate_out","n_in","n_out"), s) %in% names(t)) &&
                      any(!is.na(suppressWarnings(as.numeric(t[[paste0("rate_in", s)]]))))
MS <- Filter(function(m) all(sapply(TB, has, s=m$s)), MS)
INK <- "#0b0b0b"; INK2 <- "#52514e"; GRID <- "#e6e5e1"; SURF <- "#fcfcfb"; BAR <- "#2a78d6"
dir.create(OUT, showWarnings=FALSE, recursive=TRUE)
nc <- length(arms) * length(MS)
png(file.path(OUT, sprintf("D_hist_%s.png", HEAD)), width=520*nc, height=1400, res=220, type="quartz", bg=SURF)
par(family="HiraginoSans-W3", mfrow=c(2, nc), mar=c(3.2,2.4,2.2,0.6), oma=c(3.2,3,4.5,0.5), bg=SURF, col=INK)
rows <- list()
for (L in c(6,3)) for (i in seq_along(arms)) for (m in MS) {
  t <- TB[[i]]; num <- function(k) suppressWarnings(as.numeric(t[[paste0(k, m$s)]]))
  ri <- num("rate_in"); ro <- num("rate_out"); ni <- num("n_in"); no <- num("n_out")
  ok <- t[[paste0("L", L)]] == 1 & !is.na(ri) & !is.na(ro) & ri <= 0.05 & ni >= 20 & no >= 20
  x <- ro[ok]
  hist(x, breaks=seq(0, 1, 0.05), col=adjustcolor(BAR, .6), border=SURF, main="", xlab="", ylab="", axes=FALSE, xlim=c(0,1))
  axis(1, at=seq(0,1,.5), col=GRID, col.axis=INK2, cex.axis=.7, lwd=.6); axis(2, col=GRID, col.axis=INK2, cex.axis=.7, lwd=.6, las=1)
  title(main=sprintf("L=%d｜%s｜%s", L, nlab[i], m$lab), cex.main=.72, col.main=INK, font.main=1, line=.6)
  mtext(sprintf("定義 %d｜外の率 中央 %s", length(x), if (length(x)) sprintf("%.2f", median(x)) else "—"), side=1, line=2.0, cex=.52, col=INK2)
  rows[[length(rows)+1]] <- data.frame(arm=arms[i], L=L, 物差し=m$lab, 定義=length(x),
                                       外の率_中央=if (length(x)) median(x) else NA,
                                       外の率_0.5以上=sum(x >= .5))
}
mtext("横＝外での世界偽の率（内の率 5% 以下・内外とも主張 20 本以上の定義）", side=1, outer=TRUE, line=1.2, cex=.75, col=INK)
mtext("定義の数", side=2, outer=TRUE, line=1.2, cex=.75, col=INK)
mtext(sprintf("%s：中心的過程を通り、内でほとんど外さない定義の、外での外し方", HEAD), side=3, outer=TRUE, line=2.4, cex=.9, col=INK)
mtext("水準2・世界不明は除く／幅 0.05 の棒", side=3, outer=TRUE, line=0.9, cex=.6, col=INK2)
dev.off()
write.csv(do.call(rbind, rows), file.path(OUT, sprintf("D_hist_%s.csv", HEAD)), row.names=FALSE)
cat("図と表を書いた:", OUT, "\n")
