// Rules configuration panel logic
(function() {
    'use strict';

    var STORAGE_KEY = 'pbi-rules-config';

    function getConfig() {
        try {
            var stored = localStorage.getItem(STORAGE_KEY);
            if (stored) return JSON.parse(stored);
        } catch(e) {}
        return { disabled_rules: [], thresholds: {} };
    }

    function saveConfig(config) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
        // Sync to hidden form field
        var hidden = document.getElementById('rules-config-input');
        if (hidden) hidden.value = JSON.stringify(config);
    }

    document.addEventListener('DOMContentLoaded', function() {
        var modal = document.getElementById('rulesConfigModal');
        if (!modal) return;

        var config = getConfig();

        // Initialize toggle states
        var toggles = modal.querySelectorAll('.rule-toggle');
        toggles.forEach(function(toggle) {
            var ruleId = toggle.getAttribute('data-rule');
            toggle.checked = config.disabled_rules.indexOf(ruleId) === -1;
        });

        // Initialize threshold inputs
        var thresholdInputs = modal.querySelectorAll('.threshold-input');
        thresholdInputs.forEach(function(input) {
            var key = input.getAttribute('data-threshold');
            if (config.thresholds[key] !== undefined) {
                input.value = config.thresholds[key];
            }
        });

        // Enable all
        var enableAllBtn = document.getElementById('rules-enable-all');
        if (enableAllBtn) {
            enableAllBtn.addEventListener('click', function() {
                toggles.forEach(function(t) { t.checked = true; });
            });
        }

        // Disable all
        var disableAllBtn = document.getElementById('rules-disable-all');
        if (disableAllBtn) {
            disableAllBtn.addEventListener('click', function() {
                toggles.forEach(function(t) { t.checked = false; });
            });
        }

        // Reset defaults
        var resetBtn = document.getElementById('rules-reset');
        if (resetBtn) {
            resetBtn.addEventListener('click', function() {
                toggles.forEach(function(t) { t.checked = true; });
                thresholdInputs.forEach(function(input) {
                    input.value = input.getAttribute('data-default');
                });
            });
        }

        // Apply/Save
        var applyBtn = document.getElementById('rules-apply');
        if (applyBtn) {
            applyBtn.addEventListener('click', function() {
                var disabledRules = [];
                toggles.forEach(function(toggle) {
                    if (!toggle.checked) {
                        disabledRules.push(toggle.getAttribute('data-rule'));
                    }
                });

                var thresholds = {};
                thresholdInputs.forEach(function(input) {
                    var key = input.getAttribute('data-threshold');
                    var val = parseInt(input.value, 10);
                    if (!isNaN(val)) thresholds[key] = val;
                });

                var newConfig = { disabled_rules: disabledRules, thresholds: thresholds };
                saveConfig(newConfig);

                // Close modal
                var bsModal = bootstrap.Modal.getInstance(modal);
                if (bsModal) bsModal.hide();
            });
        }

        // On page load, sync config to hidden field
        saveConfig(config);

        // Load profiles into selector
        fetch('/profiles')
            .then(function(r) { return r.json(); })
            .then(function(profiles) {
                var sel = document.getElementById('profile-selector');
                if (!sel) return;
                profiles.forEach(function(p) {
                    var opt = document.createElement('option');
                    opt.value = p.id;
                    opt.textContent = p.name + (p.is_builtin ? '' : ' (custom)');
                    sel.appendChild(opt);
                });
            })
            .catch(function() {});
    });

    // Profile management functions (global scope)
    window.loadProfile = function(profileId) {
        if (!profileId) return;
        fetch('/profiles/' + profileId + '/export')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.error) return;
                var modal = document.getElementById('rulesConfigModal');
                // Set thresholds
                modal.querySelectorAll('.threshold-input').forEach(function(input) {
                    var key = input.getAttribute('data-threshold');
                    if (data.thresholds && data.thresholds[key] !== undefined) {
                        input.value = data.thresholds[key];
                    }
                });
                // Set rule toggles
                var disabled = data.disabled_rules || [];
                modal.querySelectorAll('.rule-toggle').forEach(function(toggle) {
                    var ruleId = toggle.getAttribute('data-rule');
                    toggle.checked = disabled.indexOf(ruleId) === -1;
                });
            })
            .catch(function() {});
    };

    window.exportCurrentProfile = function() {
        var modal = document.getElementById('rulesConfigModal');
        var disabledRules = [];
        modal.querySelectorAll('.rule-toggle').forEach(function(t) {
            if (!t.checked) disabledRules.push(t.getAttribute('data-rule'));
        });
        var thresholds = {};
        modal.querySelectorAll('.threshold-input').forEach(function(input) {
            var key = input.getAttribute('data-threshold');
            var val = parseInt(input.value, 10);
            if (!isNaN(val)) thresholds[key] = val;
        });
        var profile = {
            name: 'Custom Profile',
            description: 'Exported from GridPulse',
            disabled_rules: disabledRules,
            thresholds: thresholds
        };
        var blob = new Blob([JSON.stringify(profile, null, 2)], {type: 'application/json'});
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'gridpulse-profile.json';
        a.click();
        URL.revokeObjectURL(url);
    };

    window.importProfile = function(event) {
        var file = event.target.files[0];
        if (!file) return;
        var reader = new FileReader();
        reader.onload = function(e) {
            try {
                var data = JSON.parse(e.target.result);
                fetch('/profiles/import', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                })
                .then(function(r) { return r.json(); })
                .then(function(result) {
                    if (result.id) {
                        // Reload profile into selector and auto-select it
                        window.loadProfile(result.id);
                        location.reload();
                    }
                });
            } catch(err) {}
        };
        reader.readAsText(file);
    };
})();
