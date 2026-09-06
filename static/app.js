// Shared progressive enhancement; sensitive form values stay in this page only.
(() => {
const storage = {
  get(key) { try { return sessionStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { sessionStorage.setItem(key, value); } catch {} },
  remove(key) { try { sessionStorage.removeItem(key); } catch {} },
};
function notice(message, error = false, host = document.body, signIn = false) {
  let box = host.querySelector(':scope > .feedback');
  if (!box) { box = document.createElement('div'); box.className = 'feedback'; host.append(box); }
  box.replaceChildren();
  box.classList.toggle('feedback-error', error);
  box.setAttribute('role', error ? 'alert' : 'status');
  const text = document.createElement('span'); text.textContent = message; box.append(text);
  if (signIn) {
    const link = document.createElement('a'); link.href = '/login'; link.target = '_blank'; link.rel = 'noopener';
    link.textContent = 'Sign in in a new tab'; box.append(link);
  }
  const dismiss = document.createElement('button'); dismiss.type = 'button'; dismiss.textContent = '×';
  dismiss.setAttribute('aria-label', 'Dismiss message'); dismiss.addEventListener('click', () => box.remove()); box.append(dismiss);
}
function busy(form, active, button) {
  form.dataset.busy = active ? 'true' : ''; form.setAttribute('aria-busy', String(active));
  if (active) {
    form._buttons = [...form.querySelectorAll('button')].filter(item => !item.disabled);
    form._buttons.forEach(item => { item.disabled = true; });
    if (button) {
      button._html = button.innerHTML; button.textContent = form.action.endsWith('/login') ? 'Signing in…' : 'Saving…';
      button.classList.add('is-loading');
    }
  } else {
    (form._buttons || []).forEach(item => { item.disabled = false; });
    if (button?._html !== undefined) { button.innerHTML = button._html; delete button._html; button.classList.remove('is-loading'); }
  }
}
async function readResponse(response) {
  const isJSON = (response.headers.get('content-type') || '').includes('application/json');
  const payload = isJSON ? await response.json() : await response.text();
  if (!response.ok) {
    const error = new Error(response.status >= 500 ? 'The server could not finish the request. Your input is still here.' :
      response.status === 401 ? 'Your session has expired. Sign in in a new tab, then return here.' :
      response.status === 403 ? 'Your session or permissions may have changed. Sign in again before retrying.' :
      response.status === 429 ? 'Too many attempts. Please wait a few minutes before trying again.' :
      typeof payload.detail === 'string' ? payload.detail : 'Check your input and try again. Your changes have not been cleared.');
    error.signIn = response.status === 401 || response.status === 403;
    if (!isJSON) {
      const page = new DOMParser().parseFromString(payload, 'text/html');
      error.message = page.querySelector('.auth-error')?.textContent || error.message;
      error.csrf = page.querySelector('[name="csrf_token"]')?.value;
    }
    throw error;
  }
  return {payload, isJSON};
}
function failure(error, host) {
  notice(error instanceof TypeError ? 'Connection interrupted. Your input is still here. The change may have saved—check the list in another tab before submitting again.' : error.message, true, host, error.signIn);
  if (error.csrf) host.querySelectorAll('[name="csrf_token"]').forEach(input => { input.value = error.csrf; });
}
function confirmAction(form) {
  return new Promise(resolve => {
    const modal = document.createElement('dialog'); modal.className = 'confirm-dialog';
    modal.setAttribute('aria-labelledby', 'confirm-title'); modal.setAttribute('aria-describedby', 'confirm-description');
    const content = document.createElement('div'); content.className = 'confirm-content';
    const title = document.createElement('h2'); title.id = 'confirm-title'; title.textContent = form.dataset.confirmTitle || 'Confirm action';
    const description = document.createElement('p'); description.id = 'confirm-description'; description.textContent = form.dataset.confirm;
    const controls = document.createElement('div'); controls.className = 'confirm-controls';
    const cancel = document.createElement('button'); cancel.type = 'button'; cancel.className = 'ghost'; cancel.textContent = 'Cancel';
    const accept = document.createElement('button'); accept.type = 'button'; accept.className = 'danger-button';
    accept.textContent = form.dataset.confirmTitle === 'Stop recurring entry' ? 'Stop from this month' : 'Confirm';
    cancel.addEventListener('click', () => modal.close()); accept.addEventListener('click', () => modal.close('confirmed'));
    modal.addEventListener('close', () => { const accepted = modal.returnValue === 'confirmed'; modal.remove(); resolve(accepted); }, {once:true});
    controls.append(cancel, accept); content.append(title, description, controls); modal.append(content);
    document.body.append(modal); modal.showModal(); cancel.focus();
  });
}
document.querySelectorAll('[data-open]').forEach(button => button.addEventListener('click', () => document.getElementById(button.dataset.open)?.showModal()));
document.querySelectorAll('.close').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('cancel', event => {
  if (dialog.querySelector('[data-busy="true"]')) event.preventDefault();
}));
document.querySelectorAll('.account-dropdown').forEach(menu => {
  document.addEventListener('click', event => { if (!menu.contains(event.target)) menu.open = false; });
  menu.addEventListener('keydown', event => { if (event.key === 'Escape') { menu.open = false; menu.querySelector('summary').focus(); } });
});
const contextKey = 'budget-context-' + (document.body.dataset.household || 'guest');
const monthInput = document.querySelector('input[name="month"][type="month"]');
if (monthInput) {
  const params = new URLSearchParams(); params.set('month', monthInput.value);
  const person = monthInput.form.querySelector('[name="person"]')?.value;
  if (person) params.set('person', person);
  storage.set(contextKey, params.toString());
}
document.querySelectorAll('[data-budget-tab]').forEach(link => {
  const context = new URLSearchParams(storage.get(contextKey) || ''); const safe = new URLSearchParams();
  if (/^\d{4}-\d{2}$/.test(context.get('month') || '')) safe.set('month', context.get('month'));
  if (/^\d+$/.test(context.get('person') || '')) safe.set('person', context.get('person'));
  link.href = safe.size ? '/?' + safe : '/';
});
document.querySelectorAll('.brand-home').forEach(link => link.addEventListener('click', () => storage.remove(contextKey)));
document.querySelectorAll('[data-autosubmit]:not(.complete-toggle)').forEach(control => control.addEventListener('change', () => control.form?.requestSubmit()));
document.querySelectorAll('[data-month-step]').forEach(button => button.addEventListener('click', () => {
  const input = button.form.querySelector('input[name="month"]'); const [year, month] = input.value.split('-').map(Number);
  if (!year || !month) return;
  const next = year * 12 + month - 1 + Number(button.dataset.monthStep); const nextYear = Math.floor(next / 12);
  if (nextYear < 1 || nextYear > 9999) return;
  input.value = String(nextYear).padStart(4, '0') + '-' + String(next % 12 + 1).padStart(2, '0');
  button.form.requestSubmit();
}));
document.querySelectorAll('.controls form').forEach(form => form.addEventListener('submit', () => {
  form.querySelectorAll('[data-month-step]').forEach(button => { button.disabled = true; }); notice('Loading month…');
}));
function groupCompleted(table) {
  const body = table.tBodies[0]; const rows = [...body.rows].filter(row => row.matches('[data-entry-id], [data-grocery-id]'));
  let heading = body.querySelector('.completed-heading');
  if (!heading) {
    heading = document.createElement('tr'); heading.className = 'completed-heading';
    const cell = document.createElement('td'); cell.colSpan = table.tHead.rows[0].cells.length;
    const button = document.createElement('button'); button.type = 'button'; button.className = 'completed-disclosure';
    table.dataset.completedKey = contextKey + (table.classList.contains('grocery-table') ? '-groceries' : '-budget');
    button.setAttribute('aria-expanded', storage.get(table.dataset.completedKey) !== 'closed' ? 'true' : 'false');
    button.addEventListener('click', () => {
      button.setAttribute('aria-expanded', button.getAttribute('aria-expanded') === 'true' ? 'false' : 'true');
      storage.set(table.dataset.completedKey, button.getAttribute('aria-expanded') === 'true' ? 'open' : 'closed'); groupCompleted(table);
    });
    cell.append(button); heading.append(cell); body.append(heading);
  }
  const button = heading.querySelector('button'); const count = rows.filter(row => row.classList.contains('completed')).length;
  button.textContent = (button.getAttribute('aria-expanded') === 'true' ? '▾' : '▸') + ' Completed (' + count + ')'; heading.hidden = !count;
  rows.sort((a, b) => (b.dataset.entryDate || b.dataset.groceryDate).localeCompare(a.dataset.entryDate || a.dataset.groceryDate) ||
    Number(b.dataset.entryId || b.dataset.groceryId) - Number(a.dataset.entryId || a.dataset.groceryId));
  rows.filter(row => !row.classList.contains('completed')).forEach(row => { row.hidden = false; body.append(row); });
  body.append(heading);
  rows.filter(row => row.classList.contains('completed')).forEach(row => { row.hidden = button.getAttribute('aria-expanded') !== 'true'; body.append(row); });
  let empty = table.parentElement.querySelector('.list-empty');
  if (!empty) { empty = document.createElement('p'); empty.className = 'list-empty'; table.parentElement.prepend(empty); }
  empty.textContent = rows.length ? 'All caught up. Your completed items are below.' : 'Nothing left in this list. Add an item to get started.';
  empty.hidden = rows.some(row => !row.classList.contains('completed'));
}
document.querySelectorAll('.activity-table').forEach(groupCompleted);
document.querySelectorAll('.complete-toggle').forEach(control => control.addEventListener('change', async () => {
  const original = !control.checked; const data = new FormData(control.form);
  data.set('completed', String(control.checked)); data.set('ajax', 'true'); control.disabled = true;
  try {
    const {payload} = await readResponse(await fetch(control.form.action, {method:'POST', body:data, headers:{'X-Requested-With':'fetch'}}));
    if (Boolean(payload.completed) !== control.checked) throw new Error('Completion was not confirmed. Check the list before trying again.');
    const row = control.closest('tr'); row.classList.toggle('completed', control.checked); const table = row.closest('table'); groupCompleted(table);
    if (row.hidden) table.querySelector('.completed-disclosure').focus();
    notice(control.checked ? 'Marked completed. Find it in the Completed section.' : 'Moved back to pending.');
  } catch (error) { control.checked = original; failure(error, document.body); }
  finally { control.disabled = false; }
}));
function refreshDashboardTotals() {
  let income = 0, expenses = 0;
  document.querySelectorAll('tr[data-entry-type]').forEach(row => {
    if (row.dataset.entryType === 'income') income += Number(row.dataset.amount); else expenses += Number(row.dataset.amount);
  });
  const money = value => '$' + value.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
  const balance = income - expenses;
  if (document.querySelector('.income-total')) document.querySelector('.income-total').textContent = money(income);
  if (document.querySelector('.expense-total')) document.querySelector('.expense-total').textContent = money(expenses);
  if (document.querySelector('.balance-total')) document.querySelector('.balance-total').textContent = (balance < 0 ? '-' : '') + money(Math.abs(balance));
  document.querySelector('.hero')?.classList.toggle('negative', balance < 0);
}
document.querySelectorAll('form[method="post"]').forEach(form => form.addEventListener('submit', async event => {
  event.preventDefault();
  if (form.dataset.busy === 'true' || form.dataset.confirming === 'true') return;
  if (form.dataset.confirm) {
    form.dataset.confirming = 'true'; const accepted = await confirmAction(form); form.dataset.confirming = ''; if (!accepted) return;
  }
  const data = new FormData(form); if (form.hasAttribute('data-delete-entry')) data.set('ajax', 'true');
  const submitter = event.submitter || form.querySelector('button[type="submit"]');
  const host = form.closest('.account-panel, td') ? document.body : form;
  host.querySelector(':scope > .feedback')?.remove(); busy(form, true, submitter); let navigating = false;
  try {
    const {payload, isJSON} = await readResponse(await fetch(form.action, {method:'POST', body:data, headers:{'X-Requested-With':'ux-form'}}));
    if (isJSON && payload.deleted) {
      const table = form.closest('table'); form.closest('tr').remove(); refreshDashboardTotals(); groupCompleted(table);
      table.closest('.ledger').querySelector('.section-title button')?.focus(); notice('Entry removed. Earlier months of recurring entries are unchanged.');
    } else if (isJSON && payload.redirect) {
      const url = new URL(payload.redirect, location.origin); if (url.origin !== location.origin) throw new Error('Unexpected destination. Please reload.');
      if (form.action.endsWith('/logout')) storage.remove(contextKey);
      if (!url.searchParams.has('message')) storage.set('budget-flash', form.action.endsWith('/login') ? 'Signed in successfully.' :
        form.action.endsWith('/logout') ? 'Signed out.' : url.pathname === '/login' ? 'Done. Please sign in to continue.' : 'Changes saved.');
      navigating = true; location.assign(url.href);
    } else if (!isJSON) {
      const page = new DOMParser().parseFromString(payload, 'text/html'); const error = page.querySelector('.auth-error');
      if (error) {
        const csrf = page.querySelector('[name="csrf_token"]')?.value;
        if (csrf) form.querySelectorAll('[name="csrf_token"]').forEach(input => { input.value = csrf; });
        notice(error.textContent, true, host);
      } else {
        if (!page.querySelector('main')) throw new Error('Unexpected response. Your input has been kept.');
        // Trusted same-origin server-rendered registration/invitation step.
        navigating = true; document.open(); document.write(payload); document.close();
      }
    } else throw new Error('The save was not confirmed. Check the list before trying again.');
  } catch (error) { failure(error, host); }
  finally { if (!navigating) busy(form, false, submitter); }
}));
document.querySelectorAll('[data-select]').forEach(input => input.addEventListener('click', () => input.select()));
document.querySelectorAll('[data-copy-invitation]').forEach(button => button.addEventListener('click', async () => {
  const inputs = button.closest('main').querySelectorAll('[data-select]');
  try {
    await navigator.clipboard.writeText('Join my Budget Bloom household: ' + inputs[0].value + '\nInvitation code: ' + inputs[1].value);
    notice('Invitation copied. Share it privately with the person joining your household.', false, button.closest('main'));
  } catch {
    inputs[1].focus(); inputs[1].select(); notice('Copying is unavailable. Select and copy the registration link and code above.', true, button.closest('main'));
  }
}));
const flash = storage.get('budget-flash'); if (flash) { storage.remove('budget-flash'); notice(flash); }
window.addEventListener('pageshow', () => {
  document.querySelectorAll('form[data-busy="true"]').forEach(form => busy(form, false, form.querySelector('.is-loading')));
  document.querySelectorAll('[data-month-step]').forEach(button => { button.disabled = false; });
});

const form = document.getElementById('entryForm');
const dialog = document.getElementById('entryDialog');
document.querySelectorAll('.edit').forEach(button => button.addEventListener('click', () => {
  const entry = JSON.parse(button.dataset.entry);
  form.action = `/entries/${entry.id}/edit`;
  form.description.value = entry.description;
  form.category_id.value = entry.category_id;
  form.amount.value = entry.amount;
  form.entry_date.value = entry.entry_date;
  form.entry_date.min = entry.recurring_monthly ? `${form.month.value}-01` : '';
  form.entry_date.max = entry.recurring_monthly ? form.dataset.monthEnd : '';
  form.person_id.value = entry.person_id;
  form.recurring_monthly.checked = entry.recurring_monthly;
  form.recurring_monthly.disabled = entry.recurring_monthly;
  document.getElementById('entryRepeat').hidden = entry.recurring_monthly;
  document.getElementById('entryMonthNote').hidden = !entry.recurring_monthly;
  form.querySelector(`[name="entry_type"][value="${entry.entry_type}"]`).checked = true;
  document.getElementById('entryTitle').textContent = entry.recurring_monthly ? 'Edit this month' : 'Edit entry';
  document.getElementById('entrySubmit').textContent = 'Save changes';
  dialog.showModal();
}));
dialog?.addEventListener('close', () => {
  form.reset(); form.action = '/entries';
  form.entry_date.min = ''; form.entry_date.max = '';
  form.recurring_monthly.disabled = false;
  document.getElementById('entryRepeat').hidden = false;
  document.getElementById('entryMonthNote').hidden = true;
  document.getElementById('entryTitle').textContent = 'Add entry';
  document.getElementById('entrySubmit').textContent = 'Add entry';
});

const groceryEditDialog = document.getElementById('groceryEditDialog');
const groceryEditForm = document.getElementById('groceryEditForm');
document.querySelectorAll('.grocery-edit').forEach(button => button.addEventListener('click', () => {
  groceryEditForm.action = `/groceries/${button.dataset.itemId}/edit`;
  groceryEditForm.item_name.value = button.dataset.itemName;
  groceryEditDialog.showModal();
  groceryEditForm.item_name.focus();
  groceryEditForm.item_name.select();
}));
})();
