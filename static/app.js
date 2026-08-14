document.querySelectorAll('[data-open]').forEach(button => button.addEventListener('click', () => {
  document.getElementById(button.dataset.open)?.showModal();
}));
document.querySelectorAll('.close').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('click', event => {
  if (event.target === dialog) dialog.close();
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
