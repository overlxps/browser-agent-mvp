function isoDaysFromToday(offset) {
  const day = new Date();
  day.setDate(day.getDate() + offset);
  const month = String(day.getMonth() + 1).padStart(2, '0');
  const date = String(day.getDate()).padStart(2, '0');
  return `${day.getFullYear()}-${month}-${date}`;
}

const tasks = [
  { id: 't-1', title: '整理 Sprint 复盘纪要', priority: 'high', due_date: isoDaysFromToday(-11), status: 'todo', owner: 'Lena' },
  { id: 't-2', title: '修复登录页回归问题', priority: 'high', due_date: isoDaysFromToday(-3), status: 'todo', owner: 'Ming' },
  { id: 't-3', title: '补充 Agent 评测用例', priority: 'high', due_date: isoDaysFromToday(-2), status: 'in_progress', owner: 'Chen' },
  { id: 't-4', title: '更新演示站点文案', priority: 'medium', due_date: isoDaysFromToday(1), status: 'todo', owner: 'Ava' },
  { id: 't-5', title: '整理浏览器动作白名单', priority: 'medium', due_date: isoDaysFromToday(-6), status: 'todo', owner: 'Noah' },
  { id: 't-6', title: '准备周会演示脚本', priority: 'low', due_date: isoDaysFromToday(4), status: 'todo', owner: 'Iris' },
  { id: 't-7', title: '归档上周实验截图', priority: 'low', due_date: isoDaysFromToday(-21), status: 'done', owner: 'Leo' },
  { id: 't-8', title: '同步任务环境 README', priority: 'medium', due_date: isoDaysFromToday(-13), status: 'done', owner: 'Mia' },
  { id: 't-9', title: '核对分页筛选交互', priority: 'high', due_date: isoDaysFromToday(-9), status: 'todo', owner: 'Kai' },
  { id: 't-10', title: '补充 TaskFlow 状态流转', priority: 'medium', due_date: isoDaysFromToday(0), status: 'in_progress', owner: 'Zoe' },
  { id: 't-11', title: '清理临时评测报告', priority: 'low', due_date: isoDaysFromToday(-19), status: 'done', owner: 'Ray' },
  { id: 't-12', title: '验证高优先级逾期筛选', priority: 'high', due_date: isoDaysFromToday(-4), status: 'todo', owner: 'Jun' }
];

const state = { priority: '', status: '' };
const list = document.querySelector('#tasks');
const count = document.querySelector('#result-count');
const priorityLabels = { high: '高', medium: '中', low: '低' };
const statusLabels = { todo: '待办', in_progress: '进行中', done: '已完成' };

function visibleTasks() {
  return tasks.filter((task) => (!state.priority || task.priority === state.priority) && (!state.status || task.status === state.status));
}

function render() {
  const items = visibleTasks();
  count.textContent = `显示 ${items.length} / ${tasks.length} 个任务`;
  list.innerHTML = items.map((task) => `
    <article class="task-card" data-id="${task.id}" data-priority="${task.priority}" data-due="${task.due_date}" data-status="${task.status}">
      <div>
        <h2 data-field="title">${task.title}</h2>
        <div class="task-meta">
          <span class="badge ${task.priority}">${priorityLabels[task.priority]}优先级</span>
          <span>负责人 ${task.owner}</span>
          <span>截止 ${task.due_date}</span>
        </div>
      </div>
      <label>状态
        <select data-action="status">
          <option value="todo" ${task.status === 'todo' ? 'selected' : ''}>待办</option>
          <option value="in_progress" ${task.status === 'in_progress' ? 'selected' : ''}>进行中</option>
          <option value="done" ${task.status === 'done' ? 'selected' : ''}>已完成</option>
        </select>
      </label>
    </article>
  `).join('') || '<p class="empty">没有任务符合当前条件。</p>';
}

function updateFilters() {
  state.priority = document.querySelector('#priority-filter').value;
  state.status = document.querySelector('#status-filter').value;
  render();
}

document.querySelector('#priority-filter').addEventListener('change', updateFilters);
document.querySelector('#status-filter').addEventListener('change', updateFilters);
document.querySelector('#reset-button').addEventListener('click', () => {
  state.priority = '';
  state.status = '';
  document.querySelector('#priority-filter').value = '';
  document.querySelector('#status-filter').value = '';
  render();
});

list.addEventListener('change', (event) => {
  if (event.target.dataset.action !== 'status') return;
  const card = event.target.closest('.task-card');
  const task = tasks.find((item) => item.id === card.dataset.id);
  task.status = event.target.value;
  card.dataset.status = task.status;
});

render();
