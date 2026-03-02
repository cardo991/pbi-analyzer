/**
 * DAX Editor — selection, formatting, new measures, and apply/download.
 */

// Track added new measures
var _newMeasures = [];

function editorUpdateCount() {
    var daxChecks = document.querySelectorAll('.editor-check:checked');
    var pqChecks = document.querySelectorAll('.editor-pq-check:checked');
    var total = daxChecks.length + pqChecks.length;
    var counter = document.getElementById('editor-count');
    if (counter) counter.textContent = total;

    // Toggle selected class on DAX measures
    document.querySelectorAll('.editor-measure-item').forEach(function(item) {
        var cb = item.querySelector('.editor-check') || item.querySelector('.editor-pq-check');
        if (cb) {
            item.classList.toggle('selected', cb.checked);
        }
    });
}

function editorSelectAll() {
    var checks = document.querySelectorAll('.editor-check');
    var allChecked = Array.from(checks).every(function(c) { return c.checked; });
    var newState = !allChecked;

    checks.forEach(function(c) { c.checked = newState; });
    editorUpdateCount();

    var btn = document.getElementById('editor-select-all');
    if (btn) {
        var span = btn.querySelector('span');
        var i18n = window._editorI18n || {};
        if (span) {
            span.textContent = newState ? (i18n.deselect_all || 'Deselect All') : (i18n.select_all || 'Select All');
        }
    }
}

function editorFormatOne(btn) {
    var targetId = btn.getAttribute('data-target');
    var textarea = document.getElementById(targetId);
    if (!textarea) return;

    var expr = textarea.value;
    if (!expr.trim()) return;

    btn.disabled = true;
    fetch('/editor/format-dax', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({expression: expr})
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.formatted) {
            textarea.value = data.formatted;
            // Auto-resize
            textarea.style.height = 'auto';
            textarea.style.height = textarea.scrollHeight + 'px';
        }
    })
    .finally(function() { btn.disabled = false; });
}

function editorFormatAll() {
    var textareas = document.querySelectorAll('.editor-textarea[id^="suggested-"]');
    var promises = [];

    textareas.forEach(function(textarea) {
        var expr = textarea.value;
        if (!expr.trim()) return;

        var p = fetch('/editor/format-dax', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({expression: expr})
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.formatted) {
                textarea.value = data.formatted;
                textarea.style.height = 'auto';
                textarea.style.height = textarea.scrollHeight + 'px';
            }
        });
        promises.push(p);
    });

    Promise.all(promises);
}

function editorFormatNewMeasure() {
    var textarea = document.getElementById('new-measure-dax');
    if (!textarea || !textarea.value.trim()) return;

    fetch('/editor/format-dax', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({expression: textarea.value})
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.formatted) {
            textarea.value = data.formatted;
            textarea.style.height = 'auto';
            textarea.style.height = textarea.scrollHeight + 'px';
        }
    });
}

function editorAddMeasure() {
    var table = document.getElementById('new-measure-table').value;
    var name = document.getElementById('new-measure-name').value.trim();
    var dax = document.getElementById('new-measure-dax').value.trim();
    var fmt = document.getElementById('new-measure-format').value.trim();

    if (!name || !dax) return;

    _newMeasures.push({
        table_name: table,
        name: name,
        expression: dax,
        format_string: fmt
    });

    // Clear form
    document.getElementById('new-measure-name').value = '';
    document.getElementById('new-measure-dax').value = '';
    document.getElementById('new-measure-format').value = '';

    _renderAddedMeasures();
}

function editorRemoveMeasure(idx) {
    _newMeasures.splice(idx, 1);
    _renderAddedMeasures();
}

function _renderAddedMeasures() {
    var container = document.getElementById('editor-added-measures');
    if (!container) return;

    if (_newMeasures.length === 0) {
        container.innerHTML = '';
        return;
    }

    var html = '';
    _newMeasures.forEach(function(m, i) {
        html += '<div class="d-flex align-items-center gap-2 mb-1 p-2" style="background:var(--accent-soft);border-radius:6px;">';
        html += '<span class="badge bg-primary">' + m.table_name + '</span>';
        html += '<span style="font-weight:600;color:var(--text-1);font-size:0.85rem;">' + m.name + '</span>';
        html += '<code class="small" style="color:var(--text-3);">' + m.expression.substring(0, 50) + (m.expression.length > 50 ? '...' : '') + '</code>';
        html += '<button class="btn-ghost btn-sm ms-auto" onclick="editorRemoveMeasure(' + i + ')"><i class="bi bi-x-lg"></i></button>';
        html += '</div>';
    });
    container.innerHTML = html;
}

function editorFixAll() {
    // Select all measures that have optimizer suggestions
    document.querySelectorAll('.editor-measure-item.has-suggestion').forEach(function(item) {
        var cb = item.querySelector('.editor-check') || item.querySelector('.editor-pq-check');
        if (cb) cb.checked = true;
    });
    editorUpdateCount();
    // Trigger download with all suggested fixes
    editorApplyDownload();
}

function editorApplyDownload() {
    var analysisId = window._editorAnalysisId;
    if (!analysisId) return;

    // Collect DAX changes from checked measures (only if expression actually changed)
    var daxChanges = [];
    document.querySelectorAll('.editor-check:checked').forEach(function(cb) {
        var idx = cb.getAttribute('data-index');
        var item = cb.closest('.editor-measure-item');
        var tableName = item.getAttribute('data-table');
        var measureName = item.getAttribute('data-measure');
        var textarea = document.getElementById('suggested-' + idx);
        if (textarea && textarea.value.trim()) {
            // Get original expression from the read-only <pre> in the same item
            var pre = item.querySelector('.editor-pre');
            var original = pre ? pre.textContent : '';
            // Only include if expression was actually modified from original
            if (textarea.value.trim() !== original.trim()) {
                daxChanges.push({
                    table_name: tableName,
                    measure_name: measureName,
                    new_expression: textarea.value
                });
            }
        }
    });

    // Collect relationship changes
    var relChanges = [];
    document.querySelectorAll('.rel-crossfilter').forEach(function(sel) {
        var idx = parseInt(sel.getAttribute('data-index'));
        var original = sel.getAttribute('data-original');
        if (sel.value !== original) {
            relChanges.push({index: idx, cross_filtering: sel.value});
        }
    });
    document.querySelectorAll('.rel-active').forEach(function(cb) {
        var idx = parseInt(cb.getAttribute('data-index'));
        var original = cb.getAttribute('data-original') === 'true';
        if (cb.checked !== original) {
            // Find existing or create new change entry
            var existing = relChanges.find(function(c) { return c.index === idx; });
            if (existing) {
                existing.is_active = cb.checked;
            } else {
                relChanges.push({index: idx, is_active: cb.checked});
            }
        }
    });

    // Collect PQ changes from checked queries
    var pqChanges = [];
    document.querySelectorAll('.editor-pq-check:checked').forEach(function(cb) {
        var idx = cb.getAttribute('data-pq-index');
        var item = cb.closest('.editor-measure-item');
        var tableName = item.getAttribute('data-table');
        var queryName = item.getAttribute('data-query');
        var textarea = document.getElementById('pq-code-' + idx);
        if (textarea && textarea.value.trim()) {
            var pre = item.querySelector('.editor-pq-original');
            var original = pre ? pre.textContent : '';
            if (textarea.value.trim() !== original.trim()) {
                pqChanges.push({
                    table_name: tableName,
                    query_name: queryName,
                    new_m_code: textarea.value
                });
            }
        }
    });

    if (daxChanges.length === 0 && relChanges.length === 0 && _newMeasures.length === 0 && pqChanges.length === 0) {
        alert(window._editorI18n.no_changes || 'No changes selected');
        return;
    }

    var payload = {
        dax_changes: daxChanges,
        relationship_changes: relChanges,
        new_measures: _newMeasures,
        pq_changes: pqChanges
    };

    fetch('/editor/apply/' + analysisId, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    })
    .then(function(r) {
        if (!r.ok) {
            return r.json().then(function(d) { throw new Error(d.error || 'Error'); });
        }
        return r.blob();
    })
    .then(function(blob) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'project-modified.zip';
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    })
    .catch(function(err) {
        alert('Error: ' + err.message);
    });
}
