/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { Component, useState, onMounted, onPatched, useRef } from "@odoo/owl";

class PosDashboardPro extends Component {
    static template = "pos_dashboard_pro.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.chartRefs = {
            hourly: useRef("hourlyChart"),
            store: useRef("storeChart"),
            terminal: useRef("terminalChart"),
        };
        this.state = useState({
            loading: true,
            data: null,
            dateFrom: this.defaultDateFrom(),
            dateTo: this.defaultDateTo(),
            selectedConfigs: [],
            showAllMargin: false,
            trendView: "daily",
        });

        onMounted(() => {
            this.loadData();
        });

        onPatched(() => {
            if (this.state.data && !this.state.loading && this._chartsPending) {
                this._chartsPending = false;
                this.renderCharts();
            }
        });
    }

    defaultDateFrom() {
        const d = new Date();
        d.setDate(d.getDate() - 30);
        return d.toISOString().slice(0, 10);
    }

    defaultDateTo() {
        return new Date().toISOString().slice(0, 10);
    }

    async loadData() {
        this.state.loading = true;
        try {
            const result = await rpc("/pos_dashboard_pro/data", {
                date_from: this.state.dateFrom,
                date_to: this.state.dateTo,
                config_ids: this.state.selectedConfigs.length ? this.state.selectedConfigs : null,
            });
            this.state.data = result;
        } catch (e) {
            console.error("POS Dashboard Pro: failed to load data", e);
            this.state.error = e.message || "Failed to load dashboard data";
        } finally {
            this.state.loading = false;
            this._chartsPending = true;
        }
    }

    renderCharts() {
        if (!this.state.data) return;
        const Chart = window.Chart;
        if (!Chart) return;

        if (this.chartRefs.hourly.el) {
            if (this._hourlyChart) this._hourlyChart.destroy();
            const view = this.state.trendView;
            let labels = [];
            let values = [];
            if (view === "hourly") {
                labels = this.state.data.hourly_trend.map((h) => h.hour + ":00");
                values = this.state.data.hourly_trend.map((h) => h.revenue);
            } else if (view === "daily") {
                labels = this.state.data.daily_trend.map((d) => d.date);
                values = this.state.data.daily_trend.map((d) => d.revenue);
            } else if (view === "monthly") {
                labels = this.state.data.monthly_trend.map((m) => m.month);
                values = this.state.data.monthly_trend.map((m) => m.revenue);
            } else if (view === "yearly") {
                labels = this.state.data.yearly_trend.map((y) => y.year);
                values = this.state.data.yearly_trend.map((y) => y.revenue);
            }
            this._hourlyChart = new Chart(this.chartRefs.hourly.el.getContext("2d"), {
                type: "line",
                data: {
                    labels,
                    datasets: [{
                        label: "Revenue",
                        data: values,
                        borderColor: "#714B67",
                        backgroundColor: "rgba(113,75,103,0.15)",
                        fill: true,
                        tension: 0.3,
                    }],
                },
                options: { responsive: true, plugins: { legend: { display: false } } },
            });
        }

        if (this.chartRefs.store.el) {
            if (this._storeChart) this._storeChart.destroy();
            const storePalette = ["#00A09D", "#714B67", "#E4A900", "#DC3545", "#0D6EFD", "#6F42C1", "#20A8D8"];
            this._storeChart = new Chart(this.chartRefs.store.el.getContext("2d"), {
                type: "bar",
                data: {
                    labels: this.state.data.store_comparison.map((s) => s.name),
                    datasets: [{
                        label: "Revenue by Store",
                        data: this.state.data.store_comparison.map((s) => s.revenue),
                        backgroundColor: this.state.data.store_comparison.map((s, i) => storePalette[i % storePalette.length]),
                        borderRadius: 4,
                    }],
                },
                options: { responsive: true, plugins: { legend: { display: false } } },
            });
        }

        if (this.chartRefs.terminal.el && (this.state.data.terminal_trends || []).length) {
            if (this._terminalChart) this._terminalChart.destroy();
            const allDates = [...new Set(
                this.state.data.terminal_trends.flatMap((t) => t.series.map((s) => s.date))
            )].sort();
            const palette = ["#714B67", "#00A09D", "#E4A900", "#DC3545", "#0D6EFD", "#6F42C1"];
            const datasets = this.state.data.terminal_trends.map((t, i) => {
                const byDate = Object.fromEntries(t.series.map((s) => [s.date, s.revenue]));
                return {
                    label: t.name,
                    data: allDates.map((d) => byDate[d] || 0),
                    borderColor: palette[i % palette.length],
                    backgroundColor: "transparent",
                    tension: 0.3,
                };
            });
            this._terminalChart = new Chart(this.chartRefs.terminal.el.getContext("2d"), {
                type: "line",
                data: { labels: allDates, datasets },
                options: { responsive: true, plugins: { legend: { display: true, position: "bottom" } } },
            });
        }
    }

    onFilterChange() {
        this.loadData();
    }

    toggleShowAllMargin() {
        this.state.showAllMargin = !this.state.showAllMargin;
    }

    setTrendView(view) {
        this.state.trendView = view;
        this._chartsPending = true;
        this.renderCharts();
    }

    tileClassForMethod(name) {
        const n = (name || "").toLowerCase();
        if (n.includes("cash")) return "tile-cash";
        if (n.includes("card") || n.includes("visa") || n.includes("credit")) return "tile-card";
        return "tile-other";
    }
}

registry.category("actions").add("pos_dashboard_pro", PosDashboardPro);
