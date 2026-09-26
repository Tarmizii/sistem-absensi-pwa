/* Shared, opt-in password reveal control for authenticated product pages. */
(() => {
  if (document.body.classList.contains("t04-poc-page")) return;

  document.querySelectorAll('input[type="password"]').forEach((input, index) => {
    if (input.closest(".password-input-wrap")) return;
    if (!input.id) input.id = `password-field-${index + 1}`;

    const wrapper = document.createElement("span");
    wrapper.className = "password-input-wrap";
    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);

    const toggle = document.createElement("button");
    toggle.className = "password-visibility-toggle";
    toggle.type = "button";
    toggle.textContent = "Tampilkan";
    toggle.setAttribute("aria-controls", input.id);
    toggle.setAttribute("aria-label", "Tampilkan password");
    toggle.setAttribute("aria-pressed", "false");
    toggle.addEventListener("click", () => {
      const visible = input.type === "password";
      input.type = visible ? "text" : "password";
      toggle.textContent = visible ? "Sembunyikan" : "Tampilkan";
      toggle.setAttribute("aria-label", `${visible ? "Sembunyikan" : "Tampilkan"} password`);
      toggle.setAttribute("aria-pressed", String(visible));
    });
    wrapper.appendChild(toggle);
  });
})();
