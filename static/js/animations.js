/**
 * PBI Analyzer - UI Animations
 * Score gauge, counters, progress bars, cascade
 */
document.addEventListener('DOMContentLoaded', function() {

    // --- Animated Counter ---
    function animateCounter(el, target, duration) {
        if (!el) return;
        const start = 0;
        const startTime = performance.now();

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            // Ease out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = Math.round(start + (target - start) * eased);
            el.textContent = current;

            if (progress < 1) {
                requestAnimationFrame(update);
            } else {
                el.textContent = target;
            }
        }

        requestAnimationFrame(update);
    }

    // --- SVG Gauge Animation ---
    const gauge = document.querySelector('.gauge-fill');
    const gaugeScore = document.querySelector('.gauge-score');

    if (gauge && gaugeScore) {
        const score = parseFloat(gauge.dataset.score || 0);
        const circumference = 2 * Math.PI * 90; // r=90
        const offset = circumference - (score / 100) * circumference;

        // Trigger animation after a short delay
        setTimeout(function() {
            gauge.style.strokeDashoffset = offset;
        }, 300);

        // Animate the counter
        animateCounter(gaugeScore, Math.round(score), 2000);
    }

    // --- Category Progress Bars ---
    const progressBars = document.querySelectorAll('.cat-progress-fill');
    if (progressBars.length > 0) {
        // Use IntersectionObserver for triggering when visible
        const observer = new IntersectionObserver(function(entries) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    const bar = entry.target;
                    const pct = bar.dataset.pct || 0;
                    setTimeout(function() {
                        bar.style.width = pct + '%';
                    }, 200);
                    observer.unobserve(bar);
                }
            });
        }, { threshold: 0.3 });

        progressBars.forEach(function(bar) {
            observer.observe(bar);
        });
    }

    // --- Stat Number Counters ---
    const statNumbers = document.querySelectorAll('.stat-number[data-count]');
    if (statNumbers.length > 0) {
        const observer = new IntersectionObserver(function(entries) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    const el = entry.target;
                    const target = parseInt(el.dataset.count, 10);
                    animateCounter(el, target, 1200);
                    observer.unobserve(el);
                }
            });
        }, { threshold: 0.5 });

        statNumbers.forEach(function(el) {
            observer.observe(el);
        });
    }

    // --- Cascade Animation on Scroll ---
    const cascadeItems = document.querySelectorAll('.cascade-in');
    if (cascadeItems.length > 0) {
        const observer = new IntersectionObserver(function(entries) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    entry.target.style.animationPlayState = 'running';
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });

        cascadeItems.forEach(function(item) {
            item.style.animationPlayState = 'paused';
            observer.observe(item);
        });
    }

    // --- Findings count badge animation ---
    const countBadges = document.querySelectorAll('.findings-count');
    countBadges.forEach(function(badge) {
        const count = parseInt(badge.textContent, 10);
        if (count > 0) {
            badge.classList.add('has-issues');
        } else {
            badge.classList.add('no-issues');
        }
    });
});
