const status = document.querySelector('#status');
const taskTable = document.querySelector('#task-table');
const resultTable = document.querySelector('#result-table');
const reportSelect = document.querySelector('#report-select');
const failureList = document.querySelector('#failure-list');
const categoryList = document.querySelector('#category-list');

function renderTasks(tasks) {
  taskTable.innerHTML = tasks.map((task) => `
    <tr>
      <td>${task.id}</td>
      <td>${task.site}</td>
      <td>${task.instruction || task.description}</td>
    </tr>
  `).join('');
}

function renderSummary(report) {
  document.querySelector('#success-rate').textContent = `${report.passed_count} / ${report.total}`;
  document.querySelector('#avg-duration').textContent = `${(report.average_duration_ms / 1000).toFixed(1)} 秒`;
  document.querySelector('#avg-steps').textContent = `${report.average_steps} 步`;
  document.querySelector('#avg-retries').textContent = `${report.average_retries} 次`;
  failureList.innerHTML = (report.failure_reasons.length ? report.failure_reasons : ['暂无失败记录'])
    .map((reason) => `<li>${reason}</li>`).join('');
  const categories = report.failure_categories || {};
  const entries = Object.entries(categories).sort((a, b) => b[1] - a[1]);
  categoryList.innerHTML = entries.length
    ? entries.map(([category, count]) => `<li>${category}：${count} 个任务</li>`).join('')
    : '<li>暂无失败分类数据</li>';
}

function renderReport(report) {
  renderSummary(report);
  resultTable.innerHTML = report.results.map((result) => `
    <tr>
      <td>${result.task_id}</td>
      <td><span class="badge ${result.passed ? 'pass' : 'fail'}">${result.passed ? '通过' : '失败'}</span></td>
      <td>${result.duration_ms} ms</td>
      <td>${result.step_count}</td>
      <td>${result.retry_count}</td>
      <td>${result.failure_category || '-'}</td>
      <td>${result.failure_reason || '-'}</td>
      <td>
        <ul class="check-list">
          ${result.checks.map((check) => `<li>${check.passed ? '✓' : '✗'} ${check.name} — ${check.detail}</li>`).join('')}
        </ul>
      </td>
    </tr>
  `).join('');
  status.textContent = `报告 ${report.report_id}：成功率 ${report.success_rate}% ，总耗时 ${(report.duration_ms / 1000).toFixed(1)} 秒`;
}

async function loadTasks() {
  const tasks = await fetch('/api/evals/tasks').then((response) => response.json());
  renderTasks(tasks);
}

async function loadReports() {
  const reports = await fetch('/api/evals/reports').then((response) => response.json());
  reportSelect.innerHTML = '<option value="">选择历史报告</option>' + reports.map((report) => `
    <option value="${report.report_id}">
      ${report.report_id} · ${report.passed_count}/${report.total} · ${report.created_at}
    </option>
  `).join('');
}

document.querySelector('#run-all').addEventListener('click', async () => {
  status.textContent = '正在运行全部评测…';
  const report = await fetch('/api/evals/run', { method: 'POST' }).then((response) => response.json());
  await loadReports();
  reportSelect.value = report.report_id;
  renderReport(report);
});

reportSelect.addEventListener('change', async () => {
  if (!reportSelect.value) return;
  const report = await fetch(`/api/evals/reports/${reportSelect.value}`).then((response) => response.json());
  renderReport(report);
});

loadTasks();
loadReports();
