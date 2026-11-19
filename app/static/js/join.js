/* Показать и скопировать пароль, который сайт придумал при регистрации.
   Отдельный файл: на страницах нельзя вставлять скрипт в HTML, это режет CSP. */
(function () {
  var input = document.getElementById("join-password");
  var show = document.getElementById("join-show");
  var copy = document.getElementById("join-copy");
  if (!input || !show) return;
  show.addEventListener("click", function () {
    var hidden = input.type === "password";
    input.type = hidden ? "text" : "password";
    show.textContent = hidden ? "Скрыть" : "Показать";
  });
  if (copy) copy.addEventListener("click", function () {
    var done = function () { copy.textContent = "Скопировано"; };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(input.value).then(done, done);
    } else {
      input.type = "text";
      input.select();
      done();
    }
  });
})();
