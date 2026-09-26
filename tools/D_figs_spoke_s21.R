# D の図（v2 の s21、b2 の 4 腕）を、内と外の新旧二つの物差しで並べる（2026-09-25 23 時、アストラさんの指示。封をしない記述の図。判定しない）
# tools/D_figs_spoke.R（クラウドの Code が作ったもの）の描き方を写し、腕を 4 つにした。★ 元の D_figs*.R・D_defs_*.csv には触れない。
# 一つの定義を一つの点に。横＝内の世界偽の率、縦＝外の世界偽の率（水準2）。点の大きさ＝主張の数、色と形＝またぎ有（橙▲）／無（青●）。
#   旧：内＝①>=1、外＝①=0（rate_in・rate_out）
#   新（主）：内＝t より前に「話した」場面の型、外＝そうでない（rate_in_spk・rate_out_spk）
#   副：内＝「話して開示を受けた」場面の型（rate_in_fb・rate_out_fb）
# 行：通過群 L=6・L=3（t1739 生存）。列：4 腕 × 旧・新（または旧・副）。
# 使い方  Rscript tools/D_figs_spoke_s21.R <表のある場所> <出力の場所>
a <- commandArgs(trailingOnly=TRUE)
IN <- a[1]; OUT <- a[2]
arms <- c("b2_f00_s21","b2_f025_s21","b2_hide_s21","b2_f10_s21"); flab <- c("f=0","f=0.25","f=0.5","f=1.0")
D <- do.call(rbind, lapply(arms, function(x) read.csv(file.path(IN, sprintf("defs_spoke_%s.csv", x)))))
dir.create(OUT, showWarnings=FALSE, recursive=TRUE)
COL <- c(`1`="#eb6834", `0`="#2a78d6"); PCH <- c(`1`=17, `0`=16)
INK <- "#0b0b0b"; INK2 <- "#52514e"; GRID <- "#e6e5e1"; SURF <- "#fcfcfb"
NMAX <- max(D$n_total)
panel <- function(sub, xi, yo, title){
  x <- suppressWarnings(as.numeric(sub[[xi]])); y <- suppressWarnings(as.numeric(sub[[yo]]))
  ok <- !is.na(x) & !is.na(y)
  s <- sub[ok,]; x <- x[ok]; y <- y[ok]; o <- order(-s$n_total); s <- s[o,]; x <- x[o]; y <- y[o]
  plot(NA, xlim=c(0,1), ylim=c(0,1), xlab="", ylab="", axes=FALSE, asp=1)
  abline(h=seq(0,1,.25), v=seq(0,1,.25), col=GRID, lwd=0.6)
  axis(1, at=seq(0,1,.5), col=GRID, col.axis=INK2, cex.axis=.7, lwd=0.6)
  axis(2, at=seq(0,1,.5), col=GRID, col.axis=INK2, cex.axis=.7, lwd=0.6, las=1)
  if(nrow(s)){
    cx <- 0.35 + 0.18*sqrt(s$n_total)/sqrt(NMAX)*6
    points(x, y, pch=PCH[as.character(s$matagi)], col=adjustcolor(COL[as.character(s$matagi)], .45), cex=pmin(cx,2.6))
  }
  title(main=title, cex.main=.75, col.main=INK, font.main=1, line=.6)
  mtext(sprintf("点 %d（有 %d・無 %d）｜片側0本 %d", nrow(s), sum(s$matagi==1), sum(s$matagi==0), sum(!ok)),
        side=1, line=2.0, cex=.5, col=INK2)
}
draw <- function(fname, cols, subtitle){
  png(file.path(OUT, fname), width=4200, height=1600, res=220, type="quartz", bg=SURF)
  par(family="HiraginoSans-W3", mfrow=c(2,8), mar=c(3.4,2.4,2.0,0.6), oma=c(3.5,3,4.5,0.5), bg=SURF, col=INK)
  for(L in c(6,3)) for(i in seq_along(arms)) for(m in cols){
    sub <- D[D$arm==arms[i] & D[[paste0("L",L)]]==1,]
    panel(sub, m$x, m$y, sprintf("L=%d｜%s｜%s", L, flab[i], m$lab))
  }
  mtext("横＝内での世界偽の率", side=1, outer=TRUE, line=1.2, cex=.8, col=INK)
  mtext("縦＝外での世界偽の率", side=2, outer=TRUE, line=1.2, cex=.8, col=INK)
  mtext(sprintf("v2・s21（b2 の 4 腕、seed021〜040）：中心的過程（通過群 L）の中の定義　内と外の物差し %s", subtitle), side=3, outer=TRUE, line=2.4, cex=.9, col=INK)
  mtext("●青＝またぎ無　▲橙＝またぎ有　／　点の大きさ＝主張の数（水準2・世界不明は除く）／　線は引いていない", side=3, outer=TRUE, line=0.9, cex=.6, col=INK2)
  dev.off()
}
OLD <- list(x="rate_in", y="rate_out", lab="旧（①≧1／①=0）")
SPK <- list(x="rate_in_spk", y="rate_out_spk", lab="新（話した）")
FB  <- list(x="rate_in_fb", y="rate_out_fb", lab="副（話して開示）")
draw("D_spoke_s21_旧と新.png", list(OLD, SPK), "旧と新（話した）")
draw("D_spoke_s21_旧と副.png", list(OLD, FB), "旧と副（話して開示を受けた）")
cat("図 2 枚を書いた:", OUT, "\n")
