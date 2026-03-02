/* browse.js – Filter, Sort, Infinite Scroll for /browse */

let allShapes = [];
let filteredShapes = [];
let displayedCount = 0;
let isLoading = false;
const PAGE_SIZE = 20;

const searchInput = document.getElementById('search');
const categoryFilter = document.getElementById('category-filter');
const sortOrder = document.getElementById('sort-order');
const grid = document.getElementById('shapes-grid');
const loadingEl = document.getElementById('loading');
const emptyEl = document.getElementById('empty');


function showNextPage() {
  if (isLoading) return;
  const end = Math.min(displayedCount + PAGE_SIZE, filteredShapes.length);
  if (displayedCount >= filteredShapes.length) return;

  isLoading = true;
  const fragment = document.createDocumentFragment();
  for (let i = displayedCount; i < end; i++) {
    const div = document.createElement('div');
    div.innerHTML = buildCard(filteredShapes[i]).trim();
    fragment.appendChild(div.firstChild);
  }
  grid.appendChild(fragment);
  displayedCount = end;
  isLoading = false;
}

function applyFilter() {
  const search = searchInput.value.toLowerCase().trim();
  const cat = categoryFilter.value.toLowerCase();
  const sort = sortOrder.value;

  filteredShapes = allShapes.filter(shape => {
    const matchName = shape.name.toLowerCase().includes(search)
                   || shape.keywords.toLowerCase().includes(search);
    const matchCat = cat
      ? shape.keywords.toLowerCase().split(',').map(k => k.trim()).some(k => k.includes(cat))
      : true;
    return matchName && matchCat;
  });

  filteredShapes.sort((a, b) => {
    if (sort === 'date_asc') return new Date(a.upload_date) - new Date(b.upload_date);
    if (sort === 'date_desc') return new Date(b.upload_date) - new Date(a.upload_date);
    // popular: sort by download_count desc (provided by API when sort=popular)
    if (sort === 'popular') return (b.download_count ?? 0) - (a.download_count ?? 0);
    return 0;
  });

  grid.innerHTML = '';
  displayedCount = 0;
  emptyEl.style.display = 'none';

  if (filteredShapes.length === 0) {
    emptyEl.style.display = 'block';
    return;
  }
  showNextPage();
}

function populateCategories() {
  while (categoryFilter.options.length > 1) categoryFilter.remove(1);
  const cats = new Set();
  allShapes.forEach(shape => {
    shape.keywords.split(',').forEach(k => {
      const t = k.trim();
      if (t) cats.add(t);
    });
  });
  cats.forEach(cat => {
    const opt = document.createElement('option');
    opt.value = cat.toLowerCase();
    opt.textContent = cat;
    categoryFilter.appendChild(opt);
  });
}

async function loadShapes() {
  const sort = sortOrder.value;
  loadingEl.style.display = 'block';
  grid.innerHTML = '';
  emptyEl.style.display = 'none';
  try {
    const res = await fetch(`/get_shapes?sort=${sort}`);
    allShapes = await res.json();
    populateCategories();
    applyFilter();
  } catch (err) {
    grid.innerHTML = '';
    emptyEl.textContent = window.TRANSLATIONS.load_error;
    emptyEl.style.display = 'block';
  } finally {
    loadingEl.style.display = 'none';
  }
}

let debounceTimer;
searchInput.addEventListener('input', () => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(applyFilter, 350);
});
categoryFilter.addEventListener('change', applyFilter);
sortOrder.addEventListener('change', () => {
  // reload from API when switching to/from popular (server-side sort)
  loadShapes();
});

window.addEventListener('scroll', () => {
  const { scrollTop, scrollHeight, clientHeight } = document.documentElement;
  if (scrollTop + clientHeight >= scrollHeight - 100 && !isLoading) {
    showNextPage();
  }
});

loadShapes();
