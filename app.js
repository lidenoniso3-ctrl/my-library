const DATA_URL = "data/products.json";
const PLACEHOLDER_ICONS = {
  "كتب PDF": "📕",
  "قوالب تصميم": "🎨",
  "خطوط مجانية": "✒️",
  "ملفات تعليمية": "📄",
  "أخرى": "📦"
};

let allProducts = [];
let activeCategory = "الكل";
let searchQuery = "";

function initTheme() {
  const saved = localStorage.getItem("theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const theme = saved || (prefersDark ? "dark" : "light");
  document.documentElement.setAttribute("data-theme", theme);

  document.getElementById("themeToggle").addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
  });
}

async function loadProducts() {
  try {
    const res = await fetch(DATA_URL, { cache: "no-cache" });
    if (!res.ok) throw new Error("فشل تحميل البيانات");
    const data = await res.json();
    allProducts = Array.isArray(data.items) ? data.items : [];
    renderCategories();
    renderProducts();
  } catch (err) {
    console.error(err);
    document.getElementById("productsGrid").innerHTML =
      '<div class="empty-state"><p>تعذر تحميل المنتجات. حاول لاحقًا.</p></div>';
  }
}

function renderCategories() {
  const cats = ["الكل", ...new Set(allProducts.map(p => p.category).filter(Boolean))];
  const container = document.getElementById("categories");
  if (!container) return;
  container.innerHTML = cats.map(cat => `
    <button class="category-pill ${cat === activeCategory ? "active" : ""}" data-cat="${cat}">
      ${cat}
    </button>
  `).join("");

  container.querySelectorAll(".category-pill").forEach(btn => {
    btn.addEventListener("click", () => {
      activeCategory = btn.dataset.cat;
      container.querySelectorAll(".category-pill").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      renderProducts();
    });
  });
}

function getFiltered() {
  return allProducts.filter(p => {
    const matchCat = activeCategory === "الكل" || p.category === activeCategory;
    const q = searchQuery.trim().toLowerCase();
    const matchSearch = !q ||
      (p.title || "").toLowerCase().includes(q) ||
      (p.description || "").toLowerCase().includes(q) ||
      (p.category || "").toLowerCase().includes(q);
    return matchCat && matchSearch;
  });
}

function renderProducts() {
  const grid = document.getElementById("productsGrid");
  const empty = document.getElementById("emptyState");
  if (!grid) return;
  const items = getFiltered();

  if (!items.length) {
    grid.innerHTML = "";
    if (empty) empty.hidden = false;
    return;
  }
  if (empty) empty.hidden = true;

  grid.innerHTML = items.map(p => {
    const realIndex = allProducts.indexOf(p);
    const icon = PLACEHOLDER_ICONS[p.category] || "📦";
    const imageHTML = p.image
      ? `<img src="${p.image}" alt="${escapeHtml(p.title)}" loading="lazy" />`
      : `<div class="placeholder">${icon}</div>`;

    const metaHTML = [
      p.category ? `<span class="meta-tag">${escapeHtml(p.category)}</span>` : "",
      p.size ? `<span class="meta-tag">${escapeHtml(p.size)}</span>` : "",
      p.version ? `<span class="meta-tag">v${escapeHtml(p.version)}</span>` : ""
    ].filter(Boolean).join("");

    return `
      <article class="product-card" data-index="${realIndex}" onclick="goToProduct(${realIndex})" role="link" tabindex="0">
        <div class="product-image">
          ${imageHTML}
          ${p.category ? `<span class="product-badge">${escapeHtml(p.category)}</span>` : ""}
        </div>
        <div class="product-body">
          <h3 class="product-title">${escapeHtml(p.title || "بدون عنوان")}</h3>
          ${p.description ? `<p class="product-description">${escapeHtml(p.description)}</p>` : ""}
          ${metaHTML ? `<div class="product-meta">${metaHTML}</div>` : ""}
          <a class="download-btn" href="${p.file || "#"}" download onclick="event.stopPropagation()">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            تحميل
          </a>
        </div>
      </article>
    `;
  }).join("");
}

function goToProduct(index) {
  window.location.href = `product.html?id=${index}`;
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, s => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[s]));
}

function initSearch() {
  const input = document.getElementById("searchInput");
  if (!input) return;
  let timer;
  input.addEventListener("input", e => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      searchQuery = e.target.value;
      renderProducts();
    }, 200);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = new Date().getFullYear();
  initTheme();
  initSearch();
  loadProducts();
});