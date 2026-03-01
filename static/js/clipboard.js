// Copy-to-clipboard functionality for code blocks and DAX expressions
(function() {
    'use strict';

    document.addEventListener('DOMContentLoaded', function() {
        // Target all pre>code blocks and .kpi-dax elements
        var targets = document.querySelectorAll('pre code, .kpi-dax');
        targets.forEach(function(el) {
            var wrapper = el.closest('pre') || el;
            if (wrapper.querySelector('.copy-btn')) return; // already injected

            wrapper.style.position = 'relative';

            var btn = document.createElement('button');
            btn.className = 'copy-btn';
            btn.type = 'button';
            btn.title = window._i18n_copy || 'Copy';
            btn.innerHTML = '<i class="bi bi-clipboard"></i>';

            btn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                var text = el.textContent || el.innerText;
                navigator.clipboard.writeText(text).then(function() {
                    btn.innerHTML = '<i class="bi bi-check-lg"></i>';
                    btn.classList.add('copied');
                    setTimeout(function() {
                        btn.innerHTML = '<i class="bi bi-clipboard"></i>';
                        btn.classList.remove('copied');
                    }, 1500);
                });
            });

            wrapper.appendChild(btn);
        });
    });
})();
