function practice({ questionId, marksTotal, recommendedMinutes, questionMarkdown, modelMarkdown }) {
  return {
    questionId,
    marksTotal,
    recommendedMinutes,
    answer: "",
    loading: false,
    result: null,
    error: null,
    rawResponse: null,
    showModel: false,
    renderedQuestion: "",
    renderedModel: "",
    elapsedSeconds: 0,
    elapsedFormatted: "00:00",
    _timer: null,
    _start: 0,

    init() {
      this.renderedQuestion = window.renderMarkdown(questionMarkdown || "");
      this.renderedModel = window.renderMarkdown(modelMarkdown || "");
      this._start = Date.now();
      this._timer = setInterval(() => this.tick(), 1000);
    },

    tick() {
      this.elapsedSeconds = Math.floor((Date.now() - this._start) / 1000);
      this.elapsedFormatted = window.formatSeconds(this.elapsedSeconds);
    },

    formatNum(n) {
      if (n === null || n === undefined) return "—";
      const v = Number(n);
      if (Number.isInteger(v)) return v.toString();
      return v.toFixed(1);
    },

    toggleModel() {
      this.showModel = !this.showModel;
    },

    reset() {
      this.result = null;
      this.error = null;
      this.rawResponse = null;
    },

    async submit() {
      if (!this.answer.trim()) return;
      this.loading = true;
      this.error = null;
      this.rawResponse = null;
      try {
        const resp = await fetch("/api/mark", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question_id: this.questionId,
            student_answer: this.answer,
            duration_seconds: this.elapsedSeconds,
          }),
        });
        if (!resp.ok) {
          const text = await resp.text();
          throw new Error(`HTTP ${resp.status}: ${text.slice(0, 300)}`);
        }
        const data = await resp.json();
        const r = data.result || {};
        if (r.error) {
          this.error = r.message || r.error;
          this.rawResponse = r.raw_response || null;
          this.result = null;
        } else {
          this.result = r;
        }
      } catch (e) {
        this.error = e.message || String(e);
      } finally {
        this.loading = false;
      }
    },
  };
}
window.practice = practice;
