// Measure Lineage Tree - D3.js collapsible tree visualization
(function() {
    'use strict';

    window.renderLineageTree = function(containerId, data) {
        if (!data || !data.trees || data.trees.length === 0) return;

        var container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = '';

        var width = container.clientWidth || 800;
        var marginTop = 20, marginRight = 120, marginBottom = 20, marginLeft = 160;

        // Merge all trees into a single root
        var rootData;
        if (data.trees.length === 1) {
            rootData = data.trees[0];
        } else {
            rootData = { name: "Measures", table: "", children: data.trees };
        }

        var root = d3.hierarchy(rootData);
        var dx = 28;
        var dy = (width - marginLeft - marginRight) / (1 + root.height);

        var tree = d3.tree().nodeSize([dx, dy]);
        tree(root);

        // Compute extent
        var x0 = Infinity, x1 = -Infinity;
        root.each(function(d) {
            if (d.x > x1) x1 = d.x;
            if (d.x < x0) x0 = d.x;
        });

        var svgHeight = x1 - x0 + marginTop + marginBottom + 40;

        var svg = d3.select('#' + containerId)
            .append('svg')
            .attr('width', width)
            .attr('height', svgHeight)
            .attr('viewBox', [-marginLeft, x0 - marginTop - 10, width, svgHeight])
            .style('font', '12px Inter, sans-serif');

        // Get theme colors
        var style = getComputedStyle(document.documentElement);
        var linkColor = style.getPropertyValue('--text-3').trim() || '#64748b';
        var textColor = style.getPropertyValue('--text-1').trim() || '#f0f2f5';
        var accentColor = style.getPropertyValue('--accent').trim() || '#00bfff';

        // Links
        svg.append('g')
            .attr('fill', 'none')
            .attr('stroke', linkColor)
            .attr('stroke-opacity', 0.5)
            .attr('stroke-width', 1.5)
            .selectAll('path')
            .data(root.links())
            .join('path')
            .attr('d', d3.linkHorizontal().x(function(d) { return d.y; }).y(function(d) { return d.x; }));

        // Nodes
        var node = svg.append('g')
            .selectAll('g')
            .data(root.descendants())
            .join('g')
            .attr('transform', function(d) { return 'translate(' + d.y + ',' + d.x + ')'; });

        node.append('circle')
            .attr('r', 5)
            .attr('fill', function(d) { return d.children ? accentColor : linkColor; })
            .attr('stroke', 'none');

        node.append('text')
            .attr('dy', '0.32em')
            .attr('x', function(d) { return d.children ? -10 : 10; })
            .attr('text-anchor', function(d) { return d.children ? 'end' : 'start'; })
            .attr('fill', textColor)
            .text(function(d) { return d.data.name; })
            .clone(true).lower()
            .attr('stroke', 'var(--bg-body, #060610)')
            .attr('stroke-width', 3);

        // Tooltip on hover
        node.append('title')
            .text(function(d) {
                return d.data.table ? d.data.table + '.' + d.data.name : d.data.name;
            });
    };
})();
