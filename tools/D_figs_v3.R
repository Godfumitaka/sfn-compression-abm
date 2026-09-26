# 速報の D の図（2026-09-25、封をしない記述の図。判定しない）
# analysis_pred_2026-09-22/D_figs.R（2026-09-24）の描き方を写し、腕と出力先だけを変えた。★ 元の D_figs.R・D_defs_s21.csv には触れない。
# 一つの定義を一つの点に。横＝①>=1 の世界偽率、縦＝①=0 の世界偽率（水準2）。点の大きさ＝主張の数、色と形＝またぎ有（橙▲）／無（青●）。線は引かない。
# 列：v2 f=0・v3 の主 f=0・v2 f=1.0・v3 の主 f=1.0（どれも seed001〜005）。行：通過群 L=2〜6（t1739 生存）。
arms <- c("b2_f00_s1","v3m_f00_s1","b2_f10_s1","v3m_f10_s1")
flab <- c("v2 f=0","v3の主 f=0","v2 f=1.0","v3の主 f=1.0")
D <- do.call(rbind, lapply(arms, function(a) read.csv(sprintf("analysis_pred_2026-09-22/defs_%s.csv", a))))
D$sn <- as.integer(sub("seed","",D$seed))
D <- D[D$sn <= 5,]
dir.create("analysis_v3_2026-09-25/D_figs", showWarnings=FALSE)
write.csv(D, "analysis_v3_2026-09-25/D_figs/D_defs_v3flash_s1-5.csv", row.names=FALSE)
COL <- c(`1`="#eb6834", `0`="#2a78d6"); PCH <- c(`1`=17, `0`=16)
INK <- "#0b0b0b"; INK2 <- "#52514e"; GRID <- "#e6e5e1"; SURF <- "#fcfcfb"
panel <- function(sub, title){
  ok <- !is.na(sub$rate_in) & !is.na(sub$rate_out)
  s <- sub[ok,]; s <- s[order(-s$n_total),]
  plot(NA, xlim=c(0,1), ylim=c(0,1), xlab="", ylab="", axes=FALSE, asp=1)
  abline(h=seq(0,1,.25), v=seq(0,1,.25), col=GRID, lwd=0.6)
  axis(1, at=seq(0,1,.5), col=GRID, col.axis=INK2, cex.axis=.7, lwd=0.6)
  axis(2, at=seq(0,1,.5), col=GRID, col.axis=INK2, cex.axis=.7, lwd=0.6, las=1)
  if(nrow(s)){
    cx <- 0.35 + 0.18*sqrt(s$n_total)/sqrt(max(D$n_total))*6
    points(s$rate_in, s$rate_out, pch=PCH[as.character(s$matagi)],
           col=adjustcolor(COL[as.character(s$matagi)], .45), cex=pmin(cx,2.6))
  }
  title(main=title, cex.main=.85, col.main=INK, font.main=1, line=.6)
  mtext(sprintf("点 %d（有 %d・無 %d）｜片側0本 %d", nrow(s), sum(s$matagi==1), sum(s$matagi==0), sum(!ok)),
        side=1, line=2.0, cex=.55, col=INK2)
}
png("analysis_v3_2026-09-25/D_figs/D_v3flash_通過群L_種001-005.png", width=2400, height=3000, res=220, type="quartz", bg=SURF)
par(family="HiraginoSans-W3", mfrow=c(5,4), mar=c(3.4,2.4,2.0,0.6), oma=c(3.5,3,4.5,0.5), bg=SURF, col=INK)
for(L in 2:6) for(i in seq_along(arms)){
  sub <- D[D$arm==arms[i] & D[[paste0("L",L)]]==1,]
  panel(sub, sprintf("通過群(L=%d)｜%s", L, flab[i]))
}
mtext("横＝見てきた場面（①≧1）での世界偽の率", side=1, outer=TRUE, line=1.2, cex=.8, col=INK)
mtext("縦＝見ていない場面（①=0）での世界偽の率", side=2, outer=TRUE, line=1.2, cex=.8, col=INK)
mtext("速報 D：中心的過程（通過群(L)）の中の定義　v2 と v3 の主　種 001〜005（b2_*_s1）", side=3, outer=TRUE, line=2.4, cex=.95, col=INK)
mtext("●青＝またぎ無　▲橙＝またぎ有　／　点の大きさ＝主張の数　／　水準2・線は引いていない", side=3, outer=TRUE, line=0.9, cex=.62, col=INK2)
dev.off()
cat("図 1枚と表 D_defs_v3flash_s1-5.csv を書いた\n")
