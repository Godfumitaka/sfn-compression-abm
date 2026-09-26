# 一本の定義の主張を四つに分けた世界偽の率の分布（2026-09-26 アストラさんの指示。封をしない記述の図。判定しない）
#   話した型（行を取り込み、t より前に話した）／見たが話していない型／見ていない型／行は取り込まずに話した型（四つ目）
#   どれも t より前の履歴で決める。場面の型＝motif（4 種）。
# 対象：中心的過程の通過群（L=3・6、t1739 生存）。内の率での絞り込みはしない。
# 図に入れるのは、その分けで主張 20 本以上（世界不明を除く）の定義だけ（率を読めるように）。表（defs_spoke4_*.csv）は全部の定義を持つ。
# 使い方  Rscript tools/D_seen_spoke.R <表のある場所> <出力の場所> <題の頭> <表の頭> <腕>…（腕ごとの列。f で並べるときは f の腕を並べる）
a <- commandArgs(trailingOnly=TRUE)
IN <- a[1]; OUT <- a[2]; HEAD <- a[3]; PRE <- a[4]; arms <- a[5:length(a)]
lab_arm <- function(x) {
  v <- if (grepl("^v31v2", x)) "v2" else if (grepl("^v31x_extv2", x)) "v3取込+v3.1罰" else if (grepl("^v31x_profit", x)) "D-31取込+v3罰" else if (grepl("^v31x_none", x)) "足さない+v3罰" else if (grepl("^v31a", x)) "v3.1a" else if (grepl("^v31b", x)) "v3.1b" else if (grepl("^v3c", x)) "v3" else x
  n <- if (grepl("n95", x)) " 0.95" else if (grepl("n80", x)) " 0.8" else ""
  f <- regmatches(x, regexpr("(hide|f00|f025|f10)", x)); if (grepl("alpha1", x)) f <- paste0(f, " α=1")
  paste0(v, n, " ", f)
}
# ★ 版 5 の見方（見た＝行を取り込んだ、または同化先に選ばれた）は、第 6 引数の後に "--v5" を付けて描く
V5 <- "--v5" %in% arms; arms <- setdiff(arms, "--v5")
TB <- lapply(arms, function(x) read.csv(file.path(IN, sprintf("%s_%s.csv", PRE, x))))
SX <- if (V5) "2" else ""
KS <- list(list(k=paste0("seen",SX,"_spoke"), lab="話した型"), list(k=paste0("seen",SX,"_quiet"), lab="見たが話していない型"),
           list(k=paste0("unseen",SX), lab="見ていない型"), list(k=paste0("unseen",SX,"_spoke"), lab=if (V5) "見ずに話した型" else "取り込まずに話した型"))
if (V5) HEAD <- paste0(HEAD, "_版5")
INK <- "#0b0b0b"; INK2 <- "#52514e"; GRID <- "#e6e5e1"; SURF <- "#fcfcfb"
BAR <- c(seen_spoke="#2a78d6", seen_quiet="#8a6fd1", unseen="#eb6834", unseen_spoke="#4a9d6f",
         seen2_spoke="#2a78d6", seen2_quiet="#8a6fd1", unseen2="#eb6834", unseen2_spoke="#4a9d6f")
dir.create(OUT, showWarnings=FALSE, recursive=TRUE)
nr <- 2 * length(arms)
png(file.path(OUT, sprintf("D_seen_%s.png", HEAD)), width=2400, height=520*nr, res=220, type="quartz", bg=SURF)
par(family="HiraginoSans-W3", mfrow=c(nr, 4), mar=c(3.0,2.4,2.2,0.6), oma=c(3.2,3,4.5,0.5), bg=SURF, col=INK)
rows <- list()
for (i in seq_along(arms)) for (L in c(6,3)) for (k in KS) {
  t <- TB[[i]]; num <- function(c) suppressWarnings(as.numeric(t[[c]]))
  n <- num(paste0("n_", k$k)); r <- num(paste0("rate_", k$k))
  pass <- t[[paste0("L", L)]] == 1
  ok <- pass & !is.na(n) & n >= 20 & !is.na(r)
  x <- r[ok]
  hist(x, breaks=seq(0,1,.05), col=adjustcolor(BAR[[k$k]], .65), border=SURF, main="", xlab="", ylab="", axes=FALSE, xlim=c(0,1))
  axis(1, at=seq(0,1,.5), col=GRID, col.axis=INK2, cex.axis=.7, lwd=.6); axis(2, col=GRID, col.axis=INK2, cex.axis=.7, lwd=.6, las=1)
  title(main=sprintf("%s｜L=%d｜%s", lab_arm(arms[i]), L, k$lab), cex.main=.72, col.main=INK, font.main=1, line=.6)
  tot_n <- sum(n[pass], na.rm=TRUE); tot_wf <- sum(num(paste0("wf_", k$k))[pass], na.rm=TRUE)
  mtext(sprintf("定義 %d（通過 %d）｜率 中央 %s｜主張 計 %d・世界偽 %.1f%%", length(x), sum(pass),
                if (length(x)) sprintf("%.2f", median(x)) else "—", tot_n, if (tot_n) 100*tot_wf/tot_n else NaN),
        side=1, line=2.0, cex=.48, col=INK2)
  rows[[length(rows)+1]] <- data.frame(arm=arms[i], L=L, 分け=k$lab, 通過の定義=sum(pass), 図の定義=length(x),
      率_中央=if (length(x)) median(x) else NA, 主張_計=tot_n, 世界偽_計=tot_wf, 世界偽の率_計=if (tot_n) tot_wf/tot_n else NA)
}
mtext("横＝その分けでの世界偽の率（定義ごと。その分けで主張 20 本以上の定義）", side=1, outer=TRUE, line=1.2, cex=.75, col=INK)
mtext("定義の数", side=2, outer=TRUE, line=1.2, cex=.75, col=INK)
mtext(sprintf("%s：一本の定義の主張を、場面の型の履歴（t より前）で四つに分けた世界偽の率%s", HEAD,
              if (V5) "（見た＝行を取り込んだ、または同化先に選ばれた）" else "（見た＝行を取り込んだ）"), side=3, outer=TRUE, line=2.4, cex=.85, col=INK)
mtext("中心的過程の通過群・内の率での絞り込みなし・水準2・世界不明は除く／幅 0.05 の棒", side=3, outer=TRUE, line=0.9, cex=.6, col=INK2)
dev.off()
write.csv(do.call(rbind, rows), file.path(OUT, sprintf("D_seen_%s.csv", HEAD)), row.names=FALSE)
cat("図と表を書いた:", OUT, "\n")
