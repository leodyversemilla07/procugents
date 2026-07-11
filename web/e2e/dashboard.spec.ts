import { test, expect } from "@playwright/test"
import type { Page } from "@playwright/test"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const MOCK_STATS = {
  total_analyzed: 42,
  anomalies_found: 7,
  active_alerts: 3,
  compliance_rate: 83.3,
}

const MOCK_ANALYSES = Array.from({ length: 15 }, (_, i) => ({
  id: i + 1,
  contract_id: `PO-2024-${String(i + 1).padStart(3, "0")}`,
  contract_description: `Office Equipment ${i + 1}`,
  contract_amount: 500000 + i * 100000,
  agency: i % 2 === 0 ? "DepEd" : "DOH",
  source: "PhilGEPS",
  status: "completed",
  anomalies_count: i < 3 ? 1 : 0,
  final_risk_score: i < 3 ? 4 : 2,
  alert_triggered: i < 3,
  created_at: "2026-07-11T12:00:00Z",
}))

async function setupApiMocks(page: Page) {
  await page.route("**/api/stats", async (route) => {
    await route.fulfill({ json: MOCK_STATS })
  })
  await page.route("**/api/analyses*", async (route) => {
    const url = new URL(route.request().url())
    const q = url.searchParams.get("q") || ""
    const agency = url.searchParams.get("agency") || ""
    const minRisk = url.searchParams.get("min_risk")
    const alertedOnly = url.searchParams.get("alerted_only")
    let filtered = [...MOCK_ANALYSES]
    if (q) filtered = filtered.filter((a) => a.contract_id.includes(q) || a.contract_description.toLowerCase().includes(q.toLowerCase()))
    if (agency) filtered = filtered.filter((a) => a.agency.toLowerCase().includes(agency.toLowerCase()))
    if (minRisk) filtered = filtered.filter((a) => a.final_risk_score >= Number(minRisk))
    if (alertedOnly) filtered = filtered.filter((a) => a.alert_triggered)
    await route.fulfill({ json: filtered })
  })
  await page.route("**/api/crawl", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        json: { total_analyzed: 5, total_anomalies: 2, agencies: [] },
      })
    } else {
      await route.fulfill({ json: {} })
    }
  })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page)
    await page.goto("/")
  })

  test("renders stats cards with correct values", async ({ page }) => {
    await expect(page.getByText("42")).toBeVisible()
    await expect(page.getByText("7")).toBeVisible()
    await expect(page.getByText("3")).toBeVisible()
    await expect(page.getByText("83.3%")).toBeVisible()
  })

  test("shows WebSocket status as offline when no backend", async ({ page }) => {
    const wsBadge = page.locator('[data-testid="ws-status"]')
    await expect(wsBadge).toContainText("Offline")
  })

  test("renders contract table with data", async ({ page }) => {
    await expect(page.getByText("PO-2024-001")).toBeVisible()
    await expect(page.getByText("DepEd")).toBeVisible()
    await expect(page.getByText("PhilGEPS")).toBeVisible()
  })

  test("filtering by search text narrows results", async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="e.g. NBCC"]')
    await searchInput.fill("002")
    await page.getByRole("button", { name: "Apply" }).click()
    // Should show only PO-2024-002
    await expect(page.getByText("PO-2024-002")).toBeVisible()
    await expect(page.getByText("PO-2024-001")).not.toBeVisible()
  })

  test("filtering by agency works", async ({ page }) => {
    const agencyInput = page.locator('input[placeholder*="e.g. DepEd"]')
    await agencyInput.fill("DOH")
    await page.getByRole("button", { name: "Apply" }).click()
    // Only DOH rows — all odd IDs
    for (const a of MOCK_ANALYSES.filter((a) => a.agency === "DOH").slice(0, 3)) {
      await expect(page.getByText(a.contract_id).first()).toBeVisible()
    }
  })

  test("risk filter badge toggles", async ({ page }) => {
    const riskBadge = page.getByText("4+").first()
    await riskBadge.click()
    // Should highlight and filter
    await expect(riskBadge).toHaveAttribute("data-variant", "default")
  })

  test("alerts-only filter", async ({ page }) => {
    await page.getByText("Alerts only").click()
    // Wait for re-render
    await page.waitForTimeout(300)
    // Alert-triggered rows have final_risk_score >= 4
    await expect(page.getByText("PO-2024-001")).toBeVisible()
    // Non-alert rows (index >= 3) should not appear
    await expect(page.getByText("PO-2024-004")).not.toBeVisible()
  })

  test("clear filters resets the table", async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="e.g. NBCC"]')
    await searchInput.fill("003")
    await page.getByRole("button", { name: "Apply" }).click()
    await expect(page.getByText("PO-2024-003")).toBeVisible()
    // Click Clear filters
    await page.getByText("Clear filters").click()
    await expect(page.getByText("PO-2024-001")).toBeVisible()
  })

  test("auto-crawl button triggers POST and shows status", async ({ page }) => {
    const crawlBtn = page.getByRole("button", { name: "Start Auto-Detection" })
    await crawlBtn.click()
    await expect(page.getByText("5 contracts")).toBeVisible()
  })

  test("clicking contract navigates to detail", async ({ page }) => {
    await page.getByText("PO-2024-001").click()
    await expect(page).toHaveURL(/\/contracts\/1/)
  })

  test("Analytics link navigates to analytics page", async ({ page }) => {
    await page.getByRole("link", { name: /Analytics/ }).first().click()
    await expect(page).toHaveURL(/\/analytics/)
  })

  test("Alerts link navigates to alerts page", async ({ page }) => {
    await page.getByRole("link", { name: /Alerts/ }).click()
    await expect(page).toHaveURL(/\/alerts/)
  })

  test("pagination appears when more than 10 contracts", async ({ page }) => {
    await expect(page.getByText("Page 1 of 2")).toBeVisible()
  })

  test("pagination next page works", async ({ page }) => {
    await page.getByText(/Next/).click()
    await expect(page.getByText("Page 2 of 2")).toBeVisible()
  })
})
