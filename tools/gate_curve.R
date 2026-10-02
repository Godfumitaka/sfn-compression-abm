# 門のしきい値 g の曲線の図（2026-10-02 朝の追加）。★ tools/gate_curve.py の 門の曲線.csv を読むだけ。判定しない。
# 横＝失った正解、縦＝避けた誤答（種 1〜20 の和）。行＝世界 2・世界 1、列＝全課題・ドア・通常・ドア・例外。
# 線の色＝λ（0.0187 青・0.099 橙）、線の形＝腕（A 実線・C 破線）。点は g の 8 値。g＝1.00 の点に「1.00」、g＝0.90 の点に「0.90」と書く。
# 灰色の点線＝同じ数を無作為に黙らせた期待値（腕ごと。g の点を結ぶ）。各枠の目盛りは枠ごとに違う。
# 使い方  Rscript tools/gate_curve.R <門の曲線.csv> <出力の .png>
args <- commandArgs(trailingOnly=TRUE)
D <- read.csv(args[1], check.names=FALSE)
D <- D[D[["種"]] == "1〜20",]
INK <- "#0b0b0b"; INK2 <- "#52514e"; GRID <- "#e6e5e1"; SURF <- "#fcfcfb"; RND <- "#a8a7a2"
COL <- c(lam0187="#2a78d6", lam0990="#eb6834"); LTY <- c(A=1, C=2); PCH <- c(A=16, C=17)
png(args[2], width=3000, height=2000, res=220, type="quartz", bg=SURF)
par(family="HiraginoSans-W3", mfrow=c(2,3), mar=c(4,4.2,2.4,0.8), oma=c(3.2,0,3,0), bg=SURF, col=INK)
for (w in c(2,1)) for (g in c("全課題","ドア・通常","ドア・例外")) {
  S <- D[D[["世界"]] == w & D[["群"]] == g,]
  xm <- max(c(S[["失った正解"]], S[["無作為：失った正解"]], 1)); ym <- max(c(S[["避けた誤答"]], S[["無作為：避けた誤答"]], 1))
  plot(NA, xlim=c(0, xm*1.05), ylim=c(0, ym*1.08), xlab="", ylab="", axes=FALSE)
  abline(h=pretty(c(0,ym)), v=pretty(c(0,xm)), col=GRID, lwd=0.6)
  axis(1, col=GRID, col.axis=INK2, cex.axis=.8, lwd=0.6); axis(2, col=GRID, col.axis=INK2, cex.axis=.8, lwd=0.6, las=1)
  mtext("失った正解", 1, 2.4, cex=.7, col=INK2); mtext("避けた誤答", 2, 2.9, cex=.7, col=INK2)
  mtext(sprintf("世界 %d・%s", w, g), 3, 0.6, cex=.85, adj=0)
  for (arm in unique(S[["腕"]])) {
    a <- S[S[["腕"]] == arm,]; a <- a[order(a[["g"]]),]
    k <- substr(arm, 5, 5); l <- sub(".*_", "", arm)
    lines(a[["無作為：失った正解"]], a[["無作為：避けた誤答"]], col=RND, lty=3, lwd=0.8)
    lines(a[["失った正解"]], a[["避けた誤答"]], col=COL[l], lty=LTY[k], lwd=2)
    points(a[["失った正解"]], a[["避けた誤答"]], col=SURF, bg=COL[l], pch=21, cex=1.15, lwd=1.2)
    for (gv in c(0.9, 1.0)) {
      p <- a[abs(a[["g"]] - gv) < 1e-9,]
      text(p[["失った正解"]], p[["避けた誤答"]], sprintf("%.2f", gv), pos=4, cex=.6, col=INK2)
    }
  }
}
mtext("門のしきい値 g（支持の割合が g 未満なら黙る）：避けた誤答と失った正解（種 1〜20 の和）", outer=TRUE, side=3, line=1, cex=1, adj=0.02)
par(fig=c(0,1,0,1), oma=c(0,0,0,0), mar=c(0,0,0,0), new=TRUE); plot(0,0,type="n",axes=FALSE,xlab="",ylab="")
legend("bottom", horiz=TRUE, bty="n", cex=.8, text.col=INK,
       legend=c("A λ0.0187","A λ0.099","C λ0.0187","C λ0.099","無作為に黙らせた期待値"),
       col=c(COL["lam0187"],COL["lam0990"],COL["lam0187"],COL["lam0990"],RND), lty=c(1,1,2,2,3), lwd=c(2,2,2,2,1), pch=c(16,16,16,16,NA))
invisible(dev.off())
