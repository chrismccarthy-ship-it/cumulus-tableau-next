import { LightningElement, api, track } from 'lwc';
import createCase from '@salesforce/apex/CumulusConsoleActions.createCase';
import createTask from '@salesforce/apex/CumulusConsoleActions.createTask';
import scheduleMeeting from '@salesforce/apex/CumulusConsoleActions.scheduleMeeting';
import emailReport from '@salesforce/apex/CumulusConsoleActions.emailReport';
import listScreenFlows from '@salesforce/apex/CumulusConsoleActions.listScreenFlows';

/**
 * Cumulus Action Modal — the action surface shared by the Retail RVP and Wealth Advisor consoles.
 *   mode = schedule : 3-step Schedule Review (Topic → Schedule → Confirm) with "AI Draft" agenda
 *   mode = analyze  : "Ask about …" panel — pre-filled question + (simulated) Agentforce analysis + follow-up actions
 *   mode = report   : generated report (question, analysis, findings, recommended actions) — Export PDF / Email / Slack
 *   mode = flow     : pick an active screen flow and run it inline (lightning-flow)
 *   mode = case     : create a Case pre-filled from the insight
 *   mode = task     : create a Task (action item / assign owner)
 * `context` carries the pre-fill: {title, background, scope, attendees, question, analysis, insights, accent, subjectName}
 * `analysis` = {summary, findings:[string], bars:[{label,value,pct,color}], actions:[{title,body}], caveat}
 */
export default class CumulusActionModal extends LightningElement {
    @api mode = 'schedule';
    @api context = {};
    @api accent = '#0B5CAB';

    @track step = 1;
    @track topic = '';
    @track background = '';
    @track scope = '';
    @track meetingDate = '';
    @track duration = '30';
    @track attendees = '';
    @track agenda = '';
    @track drafting = false;
    @track busy = false;
    @track status = '';
    @track statusTone = 'ok';
    @track flows = [];
    @track selectedFlow = '';
    @track flowRunning = false;
    @track caseSubject = '';
    @track caseDescription = '';
    @track question = '';
    @track showReport = false;
    @track followUp = '';

    connectedCallback() {
        const c = this.context || {};
        this.topic = c.title || '';
        this.background = c.background || '';
        this.scope = c.scope || '';
        this.attendees = c.attendees || '';
        this.question = c.question || '';
        this.caseSubject = c.title ? `${c.title}` : 'Follow-up from dashboard insight';
        this.caseDescription = c.background || '';
        const d = new Date();
        this.meetingDate = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
        if (this.mode === 'flow') this.loadFlows();
    }

    // ---------- mode flags ----------
    get isSchedule() { return this.mode === 'schedule'; }
    get isAnalyze() { return this.mode === 'analyze' && !this.showReport; }
    get isReport() { return this.mode === 'report' || (this.mode === 'analyze' && this.showReport); }
    get isFlow() { return this.mode === 'flow'; }
    get isCase() { return this.mode === 'case'; }
    get isTask() { return this.mode === 'task'; }
    get headerTitle() {
        return { schedule: 'Schedule Review', analyze: `Ask About ${this.context.domain || 'Insights'}`, report: 'Report', flow: 'Launch Flow', case: 'Create Case', task: 'Create Action Item' }[this.mode] || 'Action';
    }
    get headerSub() {
        if (this.mode === 'analyze') return this.context.modelLabel || 'Data 360 Tableau Next Semantic Model';
        return this.context.title || '';
    }
    get headerIcon() { return { schedule: '📅', analyze: '✦', report: '▤', flow: '⇶', case: '⊕', task: '☑' }[this.mode] || '•'; }
    get accentStyle() { return `--accent:${this.accent}`; }
    get statusClass() { return `status ${this.statusTone}`; }

    // ---------- schedule ----------
    get step1() { return this.step === 1; }
    get step2() { return this.step === 2; }
    get step3() { return this.step === 3; }
    get stepLabel() { return `Step ${this.step} of 3`; }
    get tabTopicClass() { return `tab ${this.step > 1 ? 'done' : 'active'}`; }
    get tabScheduleClass() { return `tab ${this.step > 2 ? 'done' : this.step === 2 ? 'active' : ''}`; }
    get tabConfirmClass() { return `tab ${this.step === 3 ? 'active' : ''}`; }
    get progressStyle() { return `width:${(this.step / 3) * 100}%`; }
    get meetingDateLabel() {
        const [y, m, d] = (this.meetingDate || '').split('-').map(Number);
        if (!y) return '';
        return new Date(y, m - 1, d).toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
    }
    get durationOptions() { return ['15', '30', '45', '60'].map((v) => ({ value: v, label: `${v} minutes`, selected: v === this.duration })); }
    get confirmSummary() {
        return `${this.meetingDateLabel} · ${this.duration} minutes · ${this.attendees || 'no attendees'}`;
    }
    onTopic(e) { this.topic = e.target.value; }
    onBackground(e) { this.background = e.target.value; }
    onScope(e) { this.scope = e.target.value; }
    onDate(e) { this.meetingDate = e.target.value; }
    onDuration(e) { this.duration = e.target.value; }
    onAttendees(e) { this.attendees = e.target.value; }
    onAgenda(e) { this.agenda = e.target.value; }
    next() { if (this.step < 3) this.step += 1; }
    back() { if (this.step > 1) this.step -= 1; }

    /** "AI Draft" — simulates Agentforce turning the live insights into an agenda (deterministic, from the insight text). */
    draftAgenda() {
        this.drafting = true;
        const ins = (this.context.insights || []).slice(0, 3);
        const lines = [];
        lines.push(`Agenda — ${this.topic}`);
        lines.push(`1. Context (5 min): ${this.background ? this.background.split('. ')[0] + '.' : 'Review the headline insight and the metric behind it.'}`);
        ins.forEach((i, k) => lines.push(`${k + 2}. ${i.title} (${k === 0 ? 10 : 5} min): ${firstSentence(i.body)} Owner to confirm root cause and a 2-week action.`));
        lines.push(`${ins.length + 2}. Decisions & owners (5 min): agree the actions, assign owners, set the review date.`);
        lines.push(`Scope: ${this.scope || 'all'} · Prepared by Agentforce from the Tableau Next insight panel.`);
        // small delay so the "drafting" state is visible in a demo
        setTimeout(() => { this.agenda = lines.join('\n'); this.drafting = false; }, 650);
    }
    async schedule() {
        this.busy = true;
        try {
            const d = this.meetingDate ? new Date(this.meetingDate + 'T00:00:00') : new Date();
            const desc = `${this.background}\n\nScope: ${this.scope}\n\n${this.agenda}`;
            const id = await scheduleMeeting({ subject: this.topic, description: desc, meetingDate: d, durationMinutes: Number(this.duration), attendees: this.attendees });
            this.setStatus(`Meeting scheduled (Event ${id}). Calendar invite queued for: ${this.attendees || 'owner'}.`, 'ok');
            this.emitDone('schedule', id);
        } catch (e) {
            this.setStatus(`Could not schedule: ${msg(e)}`, 'bad');
        } finally { this.busy = false; }
    }

    // ---------- analyze / report ----------
    get analysis() { return this.context.analysis || {}; }
    get hasBars() { return Array.isArray(this.analysis.bars) && this.analysis.bars.length > 0; }
    get bars() { return (this.analysis.bars || []).map((b) => ({ ...b, style: `width:${Math.max(2, Math.min(100, b.pct))}%;background:${b.color}` })); }
    get generatedLine() { return `Generated by Agentforce · ${new Date().toLocaleString()}`; }
    get reportTitle() { return `Report: ${this.question}`; }
    onQuestion(e) { this.question = e.target.value; }
    onFollowUp(e) { this.followUp = e.target.value; }
    reAsk() { this.dispatchEvent(new CustomEvent('reask', { detail: { question: this.question } })); }
    askFollowUp() {
        if (!this.followUp) return;
        this.question = this.followUp; this.followUp = '';
        this.dispatchEvent(new CustomEvent('reask', { detail: { question: this.question } }));
    }
    createReport() { this.showReport = true; }
    backToAnalysis() { this.showReport = false; }
    exportPdf() {
        // print only the report card: open a clean window with the report HTML
        const html = this.reportHtml();
        const w = window.open('', '_blank');
        if (w) { w.document.write(`<html><head><title>${this.reportTitle}</title><style>body{font-family:Segoe UI,Arial,sans-serif;padding:32px;color:#1a2233}h1{font-size:20px}h3{color:#64748b;font-size:12px;text-transform:uppercase;letter-spacing:.06em}li{margin:4px 0}</style></head><body>${html}</body></html>`); w.document.close(); w.focus(); setTimeout(() => w.print(), 300); this.setStatus('Report opened for PDF export.', 'ok'); }
        else this.setStatus('Pop-up blocked — allow pop-ups to export the PDF.', 'bad');
    }
    async email() {
        this.busy = true;
        try {
            const to = await emailReport({ subject: this.reportTitle, htmlBody: this.reportHtml() });
            this.setStatus(`Report e-mailed to ${to}.`, 'ok');
        } catch (e) { this.setStatus(`E-mail failed: ${msg(e)}`, 'bad'); } finally { this.busy = false; }
    }
    slack() {
        // Slack is simulated in the demo org (no Slack app connected): the message that would be posted is shown.
        this.setStatus(`Posted to #${this.context.slackChannel || 'cumulus-leadership'} (simulated): "${this.analysis.summary || this.question}"`, 'ok');
    }
    reportHtml() {
        const a = this.analysis;
        const li = (xs) => (xs || []).map((x) => `<li>${typeof x === 'string' ? x : `<b>${x.title}:</b> ${x.body}`}</li>`).join('');
        return `<h1>${this.reportTitle}</h1><p><i>${this.generatedLine}</i></p><h3>Analysis question</h3><p>${this.question}</p><h3>Agentforce analysis</h3><p><b>${a.summary || ''}</b></p><h3>Key findings</h3><ul>${li(a.findings)}</ul><h3>Recommended actions</h3><ul>${li(a.actions)}</ul><p><i>${a.caveat || ''}</i></p>`;
    }

    // ---------- flow ----------
    async loadFlows() {
        try { this.flows = await listScreenFlows(); if (this.context.flowApiName) this.selectedFlow = this.context.flowApiName; }
        catch (e) { this.setStatus(`Could not list flows: ${msg(e)}`, 'bad'); }
    }
    get flowOptions() { return (this.flows || []).map((f) => ({ value: f.apiName, label: f.label, selected: f.apiName === this.selectedFlow })); }
    get canRunFlow() { return Boolean(this.selectedFlow) && !this.flowRunning; }
    get canRunFlowDisabled() { return !this.canRunFlow; }
    get draftLabel() { return this.drafting ? 'Drafting…' : 'AI Draft'; }
    get flowInputs() {
        // passed to the flow when it declares matching input variables (ignored otherwise)
        return [{ name: 'InsightTitle', type: 'String', value: this.context.title || '' }, { name: 'InsightBody', type: 'String', value: this.context.background || '' }, { name: 'SubjectName', type: 'String', value: this.context.subjectName || '' }];
    }
    onFlow(e) { this.selectedFlow = e.target.value; }
    runFlow() { this.flowRunning = true; }
    handleFlowStatus(e) {
        if (e.detail && (e.detail.status === 'FINISHED' || e.detail.status === 'FINISHED_SCREEN')) {
            this.flowRunning = false; this.setStatus('Flow finished.', 'ok'); this.emitDone('flow', this.selectedFlow);
        }
    }

    // ---------- case / task ----------
    onCaseSubject(e) { this.caseSubject = e.target.value; }
    onCaseDescription(e) { this.caseDescription = e.target.value; }
    async saveCase() {
        this.busy = true;
        try { const id = await createCase({ subject: this.caseSubject, description: this.caseDescription, origin: 'Tableau Next' }); this.setStatus(`Case created (${id}).`, 'ok'); this.emitDone('case', id); }
        catch (e) { this.setStatus(`Case failed: ${msg(e)}`, 'bad'); } finally { this.busy = false; }
    }
    async saveTask() {
        this.busy = true;
        try { const id = await createTask({ subject: this.caseSubject, description: this.caseDescription, dueDate: null }); this.setStatus(`Action item created (Task ${id}).`, 'ok'); this.emitDone('task', id); }
        catch (e) { this.setStatus(`Task failed: ${msg(e)}`, 'bad'); } finally { this.busy = false; }
    }
    // from the analyze panel: quick case with the analysis attached
    caseFromAnalysis() {
        this.caseSubject = `${this.context.subjectName || 'Insight'} — ${firstSentence(this.analysis.summary || this.question)}`;
        this.caseDescription = this.reportHtml().replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
        this.mode = 'case';
    }
    flowFromAnalysis() { this.mode = 'flow'; this.loadFlows(); }

    renderedCallback() {
        // LWC does not reliably reflect `value={x}` into <textarea>/<input> after the first render — sync explicitly
        this.template.querySelectorAll('[data-bind]').forEach((el) => { const v = this[el.dataset.bind]; if (v !== undefined && el.value !== String(v ?? '')) el.value = v ?? ''; });
    }

    // ---------- plumbing ----------
    setStatus(text, tone) { this.status = text; this.statusTone = tone; }
    emitDone(kind, id) { this.dispatchEvent(new CustomEvent('done', { detail: { kind, id } })); }
    close() { this.dispatchEvent(new CustomEvent('close')); }
    stop(e) { e.stopPropagation(); }
}

function firstSentence(s) { const t = String(s || '').trim(); const i = t.indexOf('. '); return i > 0 ? t.slice(0, i + 1) : t; }
function msg(e) { return (e && (e.body && e.body.message || e.message)) || String(e); }
