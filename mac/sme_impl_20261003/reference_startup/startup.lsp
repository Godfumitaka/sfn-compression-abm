(in-package :cl-user)
;; CLのpackage別名を用意する。照合・採点の関数は変えない。
(unless (find-package :lisp)
  (defpackage :lisp (:use :cl))
  (do-external-symbols (s :cl) (export s :lisp)))
(load "/Users/tatsu-admin/Documents/ChatGPT/New project/codex_sme_impl_2026-10-03/reference_replay_clean_01/distribution/qrgsetup.lsp")
(setf qrg::*qrg-path* "/Users/tatsu-admin/Documents/ChatGPT/New project/codex_sme_impl_2026-10-03/reference_replay_clean_01/distribution/")
(qrg:load-qrg-defsys "v4")
;; SBCLの警告の書式は文字列でないことがある。警告を隠さない。
(defun qrg::muffle-compile-sys-load-warning? (condition)
  (declare (ignore condition)) nil)
(qrg:compile-sys :sme)
(qrg:load-sys :sme)
(sme:sme-shakedown)
;; 表の期待値も実測値もLispの検査と結果から読む。
(dolist (test sme::*sme-tests*)
  (let ((instance (cdr (assoc test sme::*detailed-sme-test-results*))))
    (format t "~&SME-CODEX-ROW~C~A~C~A~C~A~C~A~C~A~C~A~%"
      #\Tab (sme::name test) #\Tab (if (sme::passed? test) 1 0)
      #\Tab (second (assoc :mh-count (sme::sme-tests test)))
      #\Tab (length (sme::mhs instance))
      #\Tab (second (assoc :mapping-count (sme::sme-tests test)))
      #\Tab (length (sme::mappings instance)))))
