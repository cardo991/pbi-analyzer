/**
 * GridPulse - Constellation Particle System
 * Floating luminous dots that connect with lines when close.
 * Adapts color to current theme (YPF blue palette).
 */
(function() {
    const canvas = document.getElementById('particles-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let width, height, particles, animFrame;
    const PARTICLE_COUNT = 80;
    const CONNECTION_DIST = 150;
    const MOUSE_DIST = 200;
    let mouse = { x: -1000, y: -1000 };

    // Theme-aware color
    function getParticleColor() {
        var theme = document.documentElement.getAttribute('data-theme') || 'dark';
        return theme === 'light' ? '0, 99, 190' : '0, 120, 232';
    }
    var pColor = getParticleColor();

    // Update color when theme changes
    var observer = new MutationObserver(function() {
        pColor = getParticleColor();
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

    function resize() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    }

    function createParticles() {
        particles = [];
        for (let i = 0; i < PARTICLE_COUNT; i++) {
            particles.push({
                x: Math.random() * width,
                y: Math.random() * height,
                vx: (Math.random() - 0.5) * 0.4,
                vy: (Math.random() - 0.5) * 0.4,
                r: Math.random() * 2 + 0.5,
                glow: Math.random() * 0.5 + 0.3,
                phase: Math.random() * Math.PI * 2,
            });
        }
    }

    function draw() {
        ctx.clearRect(0, 0, width, height);

        // Update & draw particles
        for (let i = 0; i < particles.length; i++) {
            const p = particles[i];

            // Move
            p.x += p.vx;
            p.y += p.vy;
            p.phase += 0.01;

            // Wrap around edges
            if (p.x < -10) p.x = width + 10;
            if (p.x > width + 10) p.x = -10;
            if (p.y < -10) p.y = height + 10;
            if (p.y > height + 10) p.y = -10;

            // Pulsing opacity
            const pulse = 0.5 + Math.sin(p.phase) * 0.3;
            const alpha = p.glow * pulse;

            // Draw glow
            const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 4);
            gradient.addColorStop(0, `rgba(${pColor}, ${alpha})`);
            gradient.addColorStop(1, `rgba(${pColor}, 0)`);
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r * 4, 0, Math.PI * 2);
            ctx.fillStyle = gradient;
            ctx.fill();

            // Draw core
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${pColor}, ${alpha + 0.2})`;
            ctx.fill();

            // Connect to nearby particles
            for (let j = i + 1; j < particles.length; j++) {
                const p2 = particles[j];
                const dx = p.x - p2.x;
                const dy = p.y - p2.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < CONNECTION_DIST) {
                    const lineAlpha = (1 - dist / CONNECTION_DIST) * 0.15;
                    ctx.beginPath();
                    ctx.moveTo(p.x, p.y);
                    ctx.lineTo(p2.x, p2.y);
                    ctx.strokeStyle = `rgba(${pColor}, ${lineAlpha})`;
                    ctx.lineWidth = 0.5;
                    ctx.stroke();
                }
            }

            // Connect to mouse
            const mdx = p.x - mouse.x;
            const mdy = p.y - mouse.y;
            const mDist = Math.sqrt(mdx * mdx + mdy * mdy);
            if (mDist < MOUSE_DIST) {
                const lineAlpha = (1 - mDist / MOUSE_DIST) * 0.3;
                ctx.beginPath();
                ctx.moveTo(p.x, p.y);
                ctx.lineTo(mouse.x, mouse.y);
                ctx.strokeStyle = `rgba(${pColor}, ${lineAlpha})`;
                ctx.lineWidth = 0.8;
                ctx.stroke();

                // Subtle repel
                const force = (MOUSE_DIST - mDist) / MOUSE_DIST * 0.02;
                p.vx += (mdx / mDist) * force;
                p.vy += (mdy / mDist) * force;

                // Clamp velocity
                const speed = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
                if (speed > 1.5) {
                    p.vx = (p.vx / speed) * 1.5;
                    p.vy = (p.vy / speed) * 1.5;
                }
            }

            // Dampen velocity
            p.vx *= 0.999;
            p.vy *= 0.999;
        }

        animFrame = requestAnimationFrame(draw);
    }

    // Mouse tracking
    document.addEventListener('mousemove', function(e) {
        mouse.x = e.clientX;
        mouse.y = e.clientY;
    });

    document.addEventListener('mouseleave', function() {
        mouse.x = -1000;
        mouse.y = -1000;
    });

    // Init
    window.addEventListener('resize', function() {
        resize();
    });

    resize();
    createParticles();
    draw();
})();
