document.addEventListener('DOMContentLoaded', function () {
  const flashCards = document.querySelectorAll('.flash');
  flashCards.forEach(function (element) {
    setTimeout(function () {
      element.style.opacity = '0.8';
    }, 200);
  });
});
