(() => {
  'use strict';

  const form = document.querySelector('[data-contact-form]');
  if (!form) return;

  const button = form.querySelector('[data-contact-submit]');
  if (!button) return;
  const defaultLabel = button.textContent;

  form.addEventListener('submit', (event) => {
    if (!form.checkValidity() || form.dataset.contactSubmitting === 'true') {
      if (form.dataset.contactSubmitting === 'true') event.preventDefault();
      return;
    }
    form.dataset.contactSubmitting = 'true';
    form.setAttribute('aria-busy', 'true');
    button.disabled = true;
    button.textContent = form.dataset.sendingLabel || 'Sending…';
  });

  window.addEventListener('pageshow', () => {
    delete form.dataset.contactSubmitting;
    form.removeAttribute('aria-busy');
    button.disabled = false;
    button.textContent = defaultLabel;
  });
})();
