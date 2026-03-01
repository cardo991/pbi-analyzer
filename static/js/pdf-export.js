// PDF export using html2pdf.js
function exportPDF() {
    const element = document.getElementById('report-content');
    if (!element) return;

    // Show branding header/footer for PDF
    var brandingHeader = document.getElementById('branding-header');
    var brandingFooter = document.getElementById('branding-footer');
    if (brandingHeader) brandingHeader.style.display = 'flex';
    if (brandingFooter) brandingFooter.style.display = 'block';

    // Apply high-contrast PDF mode
    document.body.classList.add('pdf-export-mode');

    // Expand all accordion items for PDF
    const accordions = document.querySelectorAll('.accordion-collapse');
    accordions.forEach(a => a.classList.add('show'));

    // Show all tab panes
    const tabPanes = document.querySelectorAll('.tab-pane');
    tabPanes.forEach(p => {
        p.classList.add('show', 'active');
        p.style.display = 'block';
    });

    // Disable animations for clean capture
    const animated = document.querySelectorAll('.cascade-in, .fade-in');
    animated.forEach(el => {
        el.style.opacity = '1';
        el.style.transform = 'none';
        el.style.animation = 'none';
    });

    const opt = {
        margin: [10, 10, 10, 10],
        filename: 'pbi-analysis-report.pdf',
        image: { type: 'jpeg', quality: 0.95 },
        html2canvas: {
            scale: 2,
            useCORS: true,
            letterRendering: true,
            backgroundColor: '#ffffff',
        },
        jsPDF: {
            unit: 'mm',
            format: 'a4',
            orientation: 'portrait',
        },
        pagebreak: { mode: ['avoid-all', 'css', 'legacy'] },
    };

    html2pdf().set(opt).from(element).save().then(() => {
        // Hide branding
        if (brandingHeader) brandingHeader.style.display = '';
        if (brandingFooter) brandingFooter.style.display = '';

        // Remove PDF mode
        document.body.classList.remove('pdf-export-mode');

        // Restore animations
        animated.forEach(el => {
            el.style.opacity = '';
            el.style.transform = '';
            el.style.animation = '';
        });

        // Restore accordion state
        accordions.forEach(a => a.classList.remove('show'));

        // Restore tab state
        tabPanes.forEach((p, i) => {
            if (i > 0) {
                p.classList.remove('show', 'active');
                p.style.display = '';
            }
        });
    });
}
