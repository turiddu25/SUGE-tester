function examMode({ sessionId, durationSeconds, questionIds }) {
  return {
    sessionId,
    questionIds,
    answers: Object.fromEntries(questionIds.map((id) => [id, ""])),
    flags: Object.fromEntries(questionIds.map((id) => [id, false])),
    timeLeft: durationSeconds,
    timeFormatted: window.formatSeconds(durationSeconds),
    submitting: false,
    confirmOpen: false,
    markedCount: 0,
    _timer: null,

    init() {
      this._timer = setInterval(() => this.tick(), 1000);
      window.addEventListener("beforeunload", (e) => {
        if (!this.submitting && this.hasAnyAnswer()) {
          e.preventDefault();
          e.returnValue = "";
        }
      });
    },

    hasAnyAnswer() {
      return Object.values(this.answers).some((v) => (v || "").trim().length > 0);
    },

    tick() {
      this.timeLeft = Math.max(0, this.timeLeft - 1);
      this.timeFormatted = window.formatSeconds(this.timeLeft);
      if (this.timeLeft === 0 && !this.submitting) {
        clearInterval(this._timer);
        this.submitExam();
      }
    },

    confirmSubmit() {
      this.confirmOpen = true;
    },

    async submitExam() {
      this.confirmOpen = false;
      this.submitting = true;
      this.markedCount = 0;
      if (this._timer) { clearInterval(this._timer); this._timer = null; }
      try {
        const items = this.questionIds.map((id) => ({
          question_id: id,
          answer: this.answers[id] || "",
          flagged: !!this.flags[id],
        }));
        const fakeProgress = setInterval(() => {
          if (this.markedCount < this.questionIds.length - 1) {
            this.markedCount += 1;
          }
        }, 1500);
        const resp = await fetch("/api/exam/submit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: this.sessionId,
            items,
            duration_seconds: durationSeconds - this.timeLeft,
          }),
        });
        clearInterval(fakeProgress);
        this.markedCount = this.questionIds.length;
        if (!resp.ok) {
          let payload = null;
          try { payload = await resp.json(); } catch (e) {}
          if (resp.status === 401 && payload && payload.login_url) {
            window.location.href = payload.login_url;
            return;
          }
          const text = payload ? JSON.stringify(payload) : await resp.text();
          throw new Error(`HTTP ${resp.status}: ${text.slice(0, 300)}`);
        }
        window.location.href = `/exam-sim/results/${this.sessionId}`;
      } catch (e) {
        alert("Submit failed: " + (e.message || e));
        this.submitting = false;
      }
    },
  };
}
window.examMode = examMode;
