document.querySelectorAll('[data-open]').forEach(button => button.addEventListener('click', () => {
  document.getElementById(button.dataset.open)?.showModal();
}));
document.querySelectorAll('.close').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('click', event => {
  if (event.target === dialog) dialog.close();
}));
document.querySelectorAll('[data-autosubmit]:not(.complete-toggle)').forEach(control => control.addEventListener('change', () => control.form?.submit()));
document.querySelectorAll('.complete-toggle').forEach(control => control.addEventListener('change', async () => {
  const original = !control.checked;
  // Disabled controls are omitted from FormData, so capture the checked value first.
  const formData = new FormData(control.form);
  // Send an explicit value even if browser form serialization behavior differs.
  formData.set('completed', control.checked ? 'true' : 'false');
  formData.set('ajax', 'true');
  control.disabled = true;
  try {
    const response = await fetch(control.form.action, {
      method: 'POST', body: formData, headers: {'X-Requested-With': 'fetch'}
    });
    if (!response.ok) throw new Error('Unable to save completion');
    const result = await response.json();
    if (Boolean(result.completed) !== control.checked) throw new Error('Completion was not saved');
    const row = control.closest('tr');
    row.classList.toggle('completed', control.checked);
    const body = row.parentElement;
    [...body.rows].sort((a, b) => {
      const completed = Number(a.classList.contains('completed')) - Number(b.classList.contains('completed'));
      if (completed) return completed;
      if (control.classList.contains('grocery-toggle')) {
        return b.dataset.groceryDate.localeCompare(a.dataset.groceryDate) || Number(b.dataset.groceryId) - Number(a.dataset.groceryId);
      }
      return b.dataset.entryDate.localeCompare(a.dataset.entryDate) || Number(b.dataset.entryId) - Number(a.dataset.entryId);
    }).forEach(item => body.appendChild(item));
  } catch (error) {
    control.checked = original;
    window.alert(`Could not update this ${control.classList.contains('grocery-toggle') ? 'grocery item' : 'entry'}. Please try again.`);
  } finally {
    control.disabled = false;
  }
}));
document.querySelectorAll('form[data-confirm]:not([data-delete-entry])').forEach(form => form.addEventListener('submit', event => {
  if (!window.confirm(form.dataset.confirm)) event.preventDefault();
}));
const refreshDashboardTotals = () => {
  let income = 0, expenses = 0;
  document.querySelectorAll('tbody tr[data-entry-type]').forEach(row => {
    const amount = Number(row.dataset.amount);
    if (row.dataset.entryType === 'income') income += amount; else expenses += amount;
  });
  const money = value => `$${value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
  const balance = income - expenses;
  const hero = document.querySelector('.hero');
  if (document.querySelector('.income-total')) document.querySelector('.income-total').textContent = money(income);
  if (document.querySelector('.expense-total')) document.querySelector('.expense-total').textContent = money(expenses);
  if (document.querySelector('.balance-total')) document.querySelector('.balance-total').textContent = `${balance < 0 ? '-' : ''}${money(Math.abs(balance))}`;
  hero?.classList.toggle('negative', balance < 0);
};
document.querySelectorAll('form[data-delete-entry]').forEach(deleteForm => deleteForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (!window.confirm(deleteForm.dataset.confirm)) return;
  const button = deleteForm.querySelector('button[type="submit"], button:not([type])');
  if (button) button.disabled = true;
  try {
    const formData = new FormData(deleteForm);
    formData.set('ajax', 'true');
    const response = await fetch(deleteForm.action, {
      method: 'POST', body: formData, headers: {'X-Requested-With': 'fetch'}
    });
    if (!response.ok) throw new Error('Unable to delete entry');
    deleteForm.closest('tr').remove();
    refreshDashboardTotals();
  } catch (error) {
    if (button) button.disabled = false;
    window.alert('Could not delete this entry. Please try again.');
  }
}));
document.querySelectorAll('[data-select]').forEach(input => input.addEventListener('click', () => input.select()));
document.querySelectorAll('form[data-loading-form]').forEach(loadingForm => loadingForm.addEventListener('submit', () => {
  const button = loadingForm.querySelector('button[type="submit"]');
  if (!button) return;
  button.disabled = true;
  button.classList.add('is-loading');
  button.setAttribute('aria-busy', 'true');
}));
const form = document.getElementById('entryForm');
const dialog = document.getElementById('entryDialog');
document.querySelectorAll('.edit').forEach(button => button.addEventListener('click', () => {
  const entry = JSON.parse(button.dataset.entry);
  form.action = `/entries/${entry.id}/edit`;
  form.description.value = entry.description;
  form.category_id.value = entry.category_id;
  form.amount.value = entry.amount;
  form.entry_date.value = entry.source_entry_date || entry.entry_date;
  form.person_id.value = entry.person_id;
  form.recurring_monthly.checked = entry.recurring_monthly;
  form.querySelector(`[name="entry_type"][value="${entry.entry_type}"]`).checked = true;
  document.getElementById('entryTitle').textContent = 'Edit entry';
  document.getElementById('entrySubmit').textContent = 'Save changes';
  dialog.showModal();
}));
dialog?.addEventListener('close', () => {
  form.reset(); form.action = '/entries';
  document.getElementById('entryTitle').textContent = 'Add entry';
  document.getElementById('entrySubmit').textContent = 'Add entry';
});
