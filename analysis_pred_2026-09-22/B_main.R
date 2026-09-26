# §5 B の主（2026-09-24 15:24:53 登録）。glmer、M1→M2→M3、見る量 out:grpS、Wald 95% 区間。
suppressMessages(library(lme4))
arm <- commandArgs(TRUE)[1]
agg <- read.csv(sprintf("analysis_pred_2026-09-22/glmm_%s.csv", arm))
agg <- subset(agg, grp %in% c("S","N"))            # ★ 群P は入れない
both <- tapply(agg$side, agg$defid, function(s) all(c("in","out") %in% s))
g1 <- tapply(as.character(agg$grp), agg$defid, function(x) x[1])
nS <- sum(both & g1=="S", na.rm=TRUE); nN <- sum(both & g1=="N", na.rm=TRUE)
d <- agg[rep(seq_len(nrow(agg)), agg$n), ]
d$y <- unlist(lapply(seq_len(nrow(agg)), function(i) c(rep(1L, agg$wf[i]), rep(0L, agg$n[i]-agg$wf[i]))))
d$out <- as.integer(d$side=="out"); d$grpS <- as.integer(d$grp=="S")
d$seed <- factor(d$seed); d$defid <- factor(d$defid)
ctl <- glmerControl(optimizer="bobyqa", optCtrl=list(maxfun=2e5))
F <- list(M1 = y ~ out*grpS + (1|seed) + (1+out|seed:defid),
          M2 = y ~ out*grpS + (1+out|seed:defid),
          M3 = y ~ out*grpS + (1+out||seed:defid))
cat(sprintf("■ %s  B の主（★ 直した模型・新しい種 s21）\n", arm))
cat(sprintf("  主張 %d（世界偽 %d）  定義 群S %d／群N %d\n", nrow(d), sum(d$y),
    length(unique(d$defid[d$grpS==1])), length(unique(d$defid[d$grpS==0]))))
cat(sprintf("  ★ 両側に主張がある定義  群S %d／群N %d  （どちらかが10未満なら判定保留）\n", nS, nN))
chosen <- NULL; tag <- NULL
for(nm in names(F)){
  m <- glmer(F[[nm]], data=d, family=binomial, control=ctl)
  s <- isSingular(m); msg <- m@optinfo$conv$lme4$messages
  fe <- summary(m)$coefficients["out:grpS",]
  vc <- as.data.frame(VarCorr(m))
  cat(sprintf("  %s  特異 %s  収束 %s\n", nm, s, if(is.null(msg)) "警告なし" else paste(msg,collapse=" | ")))
  cat(sprintf("      out:grpS  推定 %+.4f  SE %.4f  95%%区間 [%+.4f, %+.4f]\n", fe[1], fe[2], fe[1]-1.96*fe[2], fe[1]+1.96*fe[2]))
  for(i in seq_len(nrow(vc))) cat(sprintf("      変量 %-12s %-12s %-6s SD %.4f\n", vc$grp[i], vc$var1[i], ifelse(is.na(vc$var2[i]),"",vc$var2[i]), vc$sdcor[i]))
  chosen <- m; tag <- nm
  if(!s) break
}
fe <- summary(chosen)$coefficients
e <- fe["out:grpS",1]; se <- fe["out:grpS",2]; lo <- e-1.96*se; hi <- e+1.96*se
cat(sprintf("  ★ 判定に使う模型 %s（特異 %s）\n", tag, isSingular(chosen)))
for(i in seq_len(nrow(fe))) cat(sprintf("      固定 %-12s %+8.4f  SE %.4f\n", rownames(fe)[i], fe[i,1], fe[i,2]))
v <- if(nS<10 || nN<10) "判定保留（両側に主張のある定義が10本未満）" else
     if(lo>0) "当たり" else if(hi<0) "逆" else "外れ（区間が0を含む）"
cat(sprintf("RESULT arm=%s model=%s singular=%s est=%.4f se=%.4f lo=%.4f hi=%.4f nS=%d nN=%d verdict=%s\n",
    arm, tag, isSingular(chosen), e, se, lo, hi, nS, nN, v))
