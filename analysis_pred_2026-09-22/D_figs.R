# D の図（2026-09-24、封をしない記述の図。判定しない）
# 一つの定義を一つの点に。横＝①>=1 の世界偽率、縦＝①=0 の世界偽率（水準2）
# 点の大きさ＝主張の数（平方根）、色と形＝またぎ有（橙▲）／無（青●）
# 線は引かない（2026-09-22 追補4 §1「線を使わない散布図」）
arms <- c("b2_f00_s21","b2_f025_s21","b2_hide_s21","b2_f10_s21")
flab <- c("f=0","f=0.25","f=0.5","f=1.0")
D <- do.call(rbind, lapply(arms, function(a) read.csv(sprintf("analysis_pred_2026-09-22/defs_%s.csv", a))))
D$sn <- as.integer(sub("seed","",D$seed))
write.csv(D, "analysis_astra/D_figs_2026-09-24/D_defs_s21.csv", row.names=FALSE)
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
figL <- function(rows, file, head){
  png(file, width=2400, height=3000, res=220, type="quartz", bg=SURF)
  par(family="HiraginoSans-W3", mfrow=c(5,4), mar=c(3.4,2.4,2.0,0.6), oma=c(3.5,3,4.5,0.5), bg=SURF, col=INK)
  for(L in 2:6) for(i in seq_along(arms)){
    sub <- rows[rows$arm==arms[i] & rows[[paste0("L",L)]]==1,]
    panel(sub, sprintf("通過群(L=%d)｜%s", L, flab[i]))
  }
  mtext("横＝見てきた場面（①≧1）での世界偽の率", side=1, outer=TRUE, line=1.2, cex=.8, col=INK)
  mtext("縦＝見ていない場面（①=0）での世界偽の率", side=2, outer=TRUE, line=1.2, cex=.8, col=INK)
  mtext(head, side=3, outer=TRUE, line=2.4, cex=.95, col=INK)
  mtext("●青＝またぎ無　▲橙＝またぎ有　／　点の大きさ＝主張の数　／　★ 直した模型・水準2・新しい種 s21・線は引いていない",
        side=3, outer=TRUE, line=0.9, cex=.62, col=INK2)
  dev.off()
}
figN <- function(file){
  png(file, width=2400, height=1900, res=220, type="quartz", bg=SURF)
  par(family="HiraginoSans-W3", mfrow=c(3,4), mar=c(3.4,2.4,2.0,0.6), oma=c(3.5,3,4.5,0.5), bg=SURF, col=INK)
  sets <- list(list("種 021〜040", D), list("種 021〜030", D[D$sn<=30,]), list("種 031〜040", D[D$sn>=31,]))
  for(st in sets) for(i in seq_along(arms)){
    sub <- st[[2]][st[[2]]$arm==arms[i] & st[[2]]$L6==0,]
    panel(sub, sprintf("通過していない｜%s｜%s", flab[i], st[[1]]))
  }
  mtext("横＝見てきた場面（①≧1）での世界偽の率", side=1, outer=TRUE, line=1.2, cex=.8, col=INK)
  mtext("縦＝見ていない場面（①=0）での世界偽の率", side=2, outer=TRUE, line=1.2, cex=.8, col=INK)
  mtext("参考：中心的過程を通っていない定義（どの L でも通過群に入らない。途中で消えた定義を含む）", side=3, outer=TRUE, line=2.4, cex=.95, col=INK)
  mtext("●青＝またぎ無　▲橙＝またぎ有　／　点の大きさ＝主張の数　／　★ 直した模型・水準2・新しい種 s21", side=3, outer=TRUE, line=0.9, cex=.62, col=INK2)
  dev.off()
}
figL(D, "analysis_astra/D_figs_2026-09-24/D1_通過群L×腕_種021-040.png", "D：中心的過程（通過群(L)）の中の定義　種 021〜040")
figL(D[D$sn<=30,], "analysis_astra/D_figs_2026-09-24/D2_通過群L×腕_種021-030.png", "D：通過群(L)　前半 種 021〜030")
figL(D[D$sn>=31,], "analysis_astra/D_figs_2026-09-24/D3_通過群L×腕_種031-040.png", "D：通過群(L)　後半 種 031〜040")
figN("analysis_astra/D_figs_2026-09-24/D4_通過していない定義.png")
cat("図 4枚と表 D_defs_s21.csv を書いた\n")
