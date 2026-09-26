# 本番の流れ（2026-09-26 夜）：腕ごとの図（パッケージを使わない。判定しない。線は引かない）。
# 左：定義ごとに、横＝見た型の世界偽の率、縦＝見ていない型の世界偽の率（版 5）。通過群 L=6 は橙、L=3 は青、ほかは灰。点の大きさ＝主張の数。
# 右：通過群（L=3 か 6）の定義の、見ていない型の世界偽の率の分布（10 の区切り）。
# ★ 図の中の文字は英語（機械ごとに日本語のフォントが違うため）。
# 使い方  Rscript tools/prod_arm_fig.R <defs_spoke7_*.csv> <出力 png> <腕名>
a <- commandArgs(trailingOnly=TRUE)
D <- read.csv(a[1]); out <- a[2]; arm <- a[3]
num <- function(x) suppressWarnings(as.numeric(as.character(x)))
ns <- num(D$n_seen2_spoke) + num(D$n_seen2_quiet); ws <- num(D$wf_seen2_spoke) + num(D$wf_seen2_quiet)
nu <- num(D$n_unseen2) + num(D$n_unseen2_spoke); wu <- num(D$wf_unseen2) + num(D$wf_unseen2_spoke)
x <- ifelse(ns > 0, ws / ns, NA); y <- ifelse(nu > 0, wu / nu, NA)
col <- ifelse(D$L6 == 1, "#eb6834", ifelse(D$L3 == 1, "#2a78d6", "#bbbbbb"))
png(out, width=2000, height=1000, res=160)
par(mfrow=c(1,2), mar=c(4,4,3,1))
ok <- !is.na(x) & !is.na(y)
o <- order(col[ok] != "#bbbbbb")
plot(x[ok][o], y[ok][o], xlim=c(0,1), ylim=c(0,1), pch=16, col=adjustcolor(col[ok][o], .5),
     cex=pmin(0.3 + sqrt(ns[ok][o] + nu[ok][o]) / 20, 2.5),
     xlab="world-false rate, seen types (v5)", ylab="world-false rate, unseen types (v5)", main=paste(arm, ": per definition"))
mtext(sprintf("points %d (L6 orange %d, L3 blue %d, others grey); size = claims", sum(ok), sum(ok & D$L6 == 1), sum(ok & D$L3 == 1 & D$L6 != 1)), cex=.7)
p <- (D$L6 == 1 | D$L3 == 1) & !is.na(y)
h <- table(cut(y[p], breaks=seq(0, 1, .1), include.lowest=TRUE, right=FALSE))
barplot(h, las=2, cex.names=.7, main="pass group (L3 or L6): world-false rate, unseen types", ylab="definitions")
mtext(sprintf("pass group %d definitions; no unseen-type claims %d", sum(D$L6 == 1 | D$L3 == 1), sum((D$L6 == 1 | D$L3 == 1) & is.na(y))), cex=.7)
invisible(dev.off())
