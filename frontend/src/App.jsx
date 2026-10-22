import React, { useState, useEffect, useCallback } from 'react';
import {
  Search,
  SlidersHorizontal,
  BookOpen,
  Users,
  Building2,
  Tag,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
  Info,
  X,
  RotateCcw,
  Sparkles,
  Calendar,
} from 'lucide-react';
import { api, getToken, setToken } from './api';
import Navbar from './components/Navbar';
import AuthModal from './components/AuthModal';
import BookDetailModal from './components/BookDetailModal';
import MyLibraryView from './components/MyLibraryView';
import AdminPanel from './components/AdminPanel';
import SearchableFilterSelect from './components/SearchableFilterSelect';

export default function App() {
  const [activeTab, setActiveTab] = useState('catalog'); // 'catalog' | 'mylibrary' | 'admin'
  const [user, setUser] = useState(null);
  const [authModalMode, setAuthModalMode] = useState(null); // null | 'login' | 'register'
  const [selectedBook, setSelectedBook] = useState(null);

  // Toast notifications
  const [toasts, setToasts] = useState([]);
  const notify = useCallback((message, type = 'info') => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  }, []);

  // Catalog & Filters state
  const [booksData, setBooksData] = useState({
    items: [],
    total: 0,
    page: 1,
    limit: 8,
    total_pages: 1,
  });
  const [loadingBooks, setLoadingBooks] = useState(true);

  const [authorsList, setAuthorsList] = useState([]);
  const [categoriesList, setCategoriesList] = useState([]);
  const [publishersList, setPublishersList] = useState([]);

  // Filter inputs
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [authorFilter, setAuthorFilter] = useState('');
  const [publisherFilter, setPublisherFilter] = useState('');
  const [sortBy, setSortBy] = useState('title');
  const [sortOrder, setSortOrder] = useState('asc');
  const [page, setPage] = useState(1);
  const [limit] = useState(8);

  // Mobile Filter Drawer state
  const [mobileFilterOpen, setMobileFilterOpen] = useState(false);

  // Check current user on mount
  useEffect(() => {
    const token = getToken();
    if (token) {
      api
        .getMe()
        .then((me) => setUser(me))
        .catch(() => {
          setToken(null);
          setUser(null);
        });
    }
  }, []);

  // Load filter dropdown options (Authors, Categories, Publishers)
  const fetchFilterMetadata = useCallback(async () => {
    try {
      const [a, c, p] = await Promise.all([
        api.getAuthors(),
        api.getCategories(),
        api.getPublishers(),
      ]);
      setAuthorsList(a || []);
      setCategoriesList(c || []);
      setPublishersList(p || []);
    } catch {
      // ignore initial metadata errors if backend is starting
    }
  }, []);

  useEffect(() => {
    fetchFilterMetadata();
  }, [fetchFilterMetadata]);

  // Load paginated & filtered books
  const fetchBooks = useCallback(async () => {
    setLoadingBooks(true);
    try {
      const res = await api.getBooks({
        page,
        limit,
        search: search.trim() || undefined,
        category: categoryFilter || undefined,
        author: authorFilter || undefined,
        publisher: publisherFilter || undefined,
        sortBy,
        sortOrder,
      });
      setBooksData(
        res || { items: [], total: 0, page: 1, limit: 8, total_pages: 1 }
      );
    } catch (err) {
      notify(err.message || 'Kitap listesi alınamadı', 'error');
    } finally {
      setLoadingBooks(false);
    }
  }, [
    page,
    limit,
    search,
    categoryFilter,
    authorFilter,
    publisherFilter,
    sortBy,
    sortOrder,
    notify,
  ]);

  useEffect(() => {
    fetchBooks();
  }, [fetchBooks]);

  const handleResetFilters = () => {
    setSearch('');
    setCategoryFilter('');
    setAuthorFilter('');
    setPublisherFilter('');
    setSortBy('title');
    setSortOrder('asc');
    setPage(1);
    setMobileFilterOpen(false);
  };

  const handleLogout = () => {
    setToken(null);
    setUser(null);
    setActiveTab('catalog');
    notify('Oturumunuz güvenli bir şekilde kapatıldı.', 'info');
  };

  const activeFilterCount = [
    search.trim(),
    categoryFilter,
    authorFilter,
    publisherFilter,
  ].filter(Boolean).length;

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
      {/* Top Navbar + Mobile Hamburger Drawer */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        user={user}
        onOpenAuth={(mode) => setAuthModalMode(mode)}
        onLogout={handleLogout}
      />

      {/* Toast Notifications Container */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full px-4 sm:px-0 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-start gap-3 p-4 rounded-2xl shadow-xl border backdrop-blur-md transition-all ${
              t.type === 'success'
                ? 'bg-emerald-950/95 text-emerald-50 border-emerald-700'
                : t.type === 'error'
                ? 'bg-rose-950/95 text-rose-50 border-rose-700'
                : 'bg-slate-900/95 text-white border-slate-700'
            }`}
          >
            {t.type === 'success' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
            ) : t.type === 'error' ? (
              <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            ) : (
              <Info className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
            )}
            <div className="flex-1 text-xs sm:text-sm font-medium leading-snug">
              {t.message}
            </div>
            <button
              onClick={() =>
                setToasts((prev) => prev.filter((item) => item.id !== t.id))
              }
              className="text-white/60 hover:text-white"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        {activeTab === 'catalog' && (
          <div className="space-y-6">
            {/* Hero Banner */}
            <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-indigo-900 via-indigo-800 to-violet-900 text-white p-6 sm:p-8 shadow-lg">
              <div className="relative z-10 max-w-2xl space-y-2">
                <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-white/15 backdrop-blur-xs text-indigo-100">
                  <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                  Dijital Katalog & Akıllı Rezervasyon Sistemi
                </div>
                <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
                  Kütüphane Kataloğunu Keşfedin
                </h1>
                <p className="text-xs sm:text-sm text-indigo-100/90 leading-relaxed">
                  Kitapları başlık, yazar, kategori veya yayınevine göre filtreleyin; stokta olan eserleri anında ödünç alın veya tükenen kitaplar için rezervasyon sırasına girin.
                </p>
              </div>
            </div>

            {/* Search & Mobile Filter Trigger Bar */}
            <div className="bg-white p-4 sm:p-5 rounded-2xl border border-slate-200/90 shadow-xs space-y-4">
              <div className="flex flex-col sm:flex-row gap-3">
                {/* Search Input */}
                <div className="relative flex-1">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    value={search}
                    onChange={(e) => {
                      setSearch(e.target.value);
                      setPage(1);
                    }}
                    placeholder="Kitap başlığında ara (Örn: Suç ve Ceza, Harry)..."
                    className="w-full pl-10 pr-9 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  />
                  {search && (
                    <button
                      onClick={() => {
                        setSearch('');
                        setPage(1);
                      }}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>

                {/* Mobile Filter Button (only visible on < lg screens) */}
                <div className="flex items-center gap-2 lg:hidden">
                  <button
                    type="button"
                    onClick={() => setMobileFilterOpen(!mobileFilterOpen)}
                    className={`flex-1 sm:flex-initial inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold border transition-all ${
                      mobileFilterOpen || activeFilterCount > 0
                        ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
                        : 'bg-slate-50 text-slate-700 border-slate-200'
                    }`}
                  >
                    <SlidersHorizontal className="w-4 h-4" />
                    <span>Filtrele & Sırala</span>
                    {activeFilterCount > 0 && (
                      <span className="px-1.5 py-0.2 rounded-full bg-indigo-600 text-white text-[10px]">
                        {activeFilterCount}
                      </span>
                    )}
                  </button>

                  {activeFilterCount > 0 && (
                    <button
                      type="button"
                      onClick={handleResetFilters}
                      className="p-2.5 rounded-xl text-slate-500 hover:text-rose-600 hover:bg-rose-50 border border-slate-200"
                      title="Filtreleri Sıfırla"
                    >
                      <RotateCcw className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>

              {/* Desktop Open Filter Bar (hidden on mobile unless mobileFilterOpen is true) */}
              <div
                className={`${
                  mobileFilterOpen ? 'grid' : 'hidden lg:grid'
                } grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 pt-3 border-t border-slate-100`}
              >
                {/* Category Filter (Aramalı Seçim) */}
                <SearchableFilterSelect
                  label="Kategori"
                  placeholder="Kategori ara veya seç..."
                  options={categoriesList.map((c) => ({
                    label: c.name,
                    value: c.name,
                  }))}
                  value={categoryFilter}
                  onChange={(val) => {
                    setCategoryFilter(val);
                    setPage(1);
                  }}
                />

                {/* Author Filter (Aramalı Seçim) */}
                <SearchableFilterSelect
                  label="Yazar"
                  placeholder="Yazar adı ara veya seç..."
                  options={authorsList.map((a) => ({
                    label: `${a.first_name} ${a.last_name}`,
                    value: a.last_name,
                  }))}
                  value={authorFilter}
                  onChange={(val) => {
                    setAuthorFilter(val);
                    setPage(1);
                  }}
                />

                {/* Publisher Filter (Aramalı Seçim) */}
                <SearchableFilterSelect
                  label="Yayınevi"
                  placeholder="Yayınevi ara veya seç..."
                  options={publishersList.map((p) => ({
                    label: p.name,
                    value: p.name,
                  }))}
                  value={publisherFilter}
                  onChange={(val) => {
                    setPublisherFilter(val);
                    setPage(1);
                  }}
                />

                {/* Sort By */}
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1">
                    Sıralama Ölçütü
                  </label>
                  <select
                    value={sortBy}
                    onChange={(e) => {
                      setSortBy(e.target.value);
                      setPage(1);
                    }}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs sm:text-sm bg-slate-50/60 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="title">Kitap Adı (A-Z)</option>
                    <option value="published_year">Yayın Yılı</option>
                    <option value="stock_count">Stok Miktarı</option>
                    <option value="isbn">ISBN</option>
                  </select>
                </div>

                {/* Sort Order & Reset */}
                <div className="flex items-end gap-2">
                  <div className="flex-1">
                    <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1">
                      Yön
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))
                      }
                      className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-slate-50/60 hover:bg-slate-100 text-xs sm:text-sm font-medium flex items-center justify-center gap-1.5 cursor-pointer"
                    >
                      <ArrowUpDown className="w-3.5 h-3.5 text-indigo-600" />
                      {sortOrder === 'asc' ? 'Artan (ASC)' : 'Azalan (DESC)'}
                    </button>
                  </div>

                  {activeFilterCount > 0 && (
                    <button
                      type="button"
                      onClick={handleResetFilters}
                      title="Filtreleri Temizle"
                      className="px-3 py-2 rounded-xl border border-rose-200 bg-rose-50 text-rose-600 hover:bg-rose-100 text-xs font-semibold flex items-center gap-1 cursor-pointer"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      Temizle
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Results Metadata Bar */}
            <div className="flex items-center justify-between text-xs text-slate-500 px-1">
              <span>
                Toplam <strong className="text-slate-800">{booksData.total}</strong> kitap bulundu
              </span>
              <span>
                Sayfa <strong className="text-slate-800">{booksData.page}</strong> /{' '}
                {booksData.total_pages || 1}
              </span>
            </div>

            {/* Responsive Book Grid: grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 */}
            {loadingBooks ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
                {[1, 2, 3, 4].map((n) => (
                  <div
                    key={n}
                    className="h-72 rounded-2xl bg-white border border-slate-200 p-5 animate-pulse flex flex-col justify-between"
                  >
                    <div className="space-y-3">
                      <div className="w-24 h-5 bg-slate-200 rounded-full" />
                      <div className="w-3/4 h-6 bg-slate-200 rounded-lg" />
                      <div className="w-1/2 h-4 bg-slate-100 rounded-lg" />
                    </div>
                    <div className="w-full h-10 bg-slate-100 rounded-xl" />
                  </div>
                ))}
              </div>
            ) : booksData.items.length === 0 ? (
              <div className="bg-white rounded-3xl p-12 text-center border border-dashed border-slate-300 max-w-lg mx-auto my-6">
                <div className="w-14 h-14 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto mb-3">
                  <BookOpen className="w-7 h-7" />
                </div>
                <h3 className="text-base font-bold text-slate-900">
                  Arama kriterlerinize uygun kitap bulunamadı
                </h3>
                <p className="text-xs text-slate-500 mt-1 mb-4">
                  Farklı anahtar kelimeler deneyebilir veya aktif filtreleri temizleyebilirsiniz.
                </p>
                {activeFilterCount > 0 && (
                  <button
                    onClick={handleResetFilters}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-700"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    Tüm Filtreleri Temizle
                  </button>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
                {booksData.items.map((book) => {
                  const inStock = book.stock_count > 0;
                  return (
                    <div
                      key={book.id}
                      onClick={() => setSelectedBook(book)}
                      className="group bg-white rounded-2xl border border-slate-200/90 hover:border-indigo-300 shadow-2xs hover:shadow-xl hover:shadow-indigo-100/50 transition-all duration-200 flex flex-col justify-between overflow-hidden cursor-pointer"
                    >
                      <div>
                        {/* Card Top Strip */}
                        <div className="p-5 pb-3 flex items-center justify-between gap-2">
                          <span
                            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold ${
                              inStock
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                : 'bg-rose-50 text-rose-700 border border-rose-200'
                            }`}
                          >
                            <span
                              className={`w-1.5 h-1.5 rounded-full ${
                                inStock ? 'bg-emerald-500' : 'bg-rose-500'
                              }`}
                            />
                            {inStock ? `Stokta: ${book.stock_count}` : 'Tükendi (0)'}
                          </span>

                          {book.published_year && (
                            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-400">
                              <Calendar className="w-3 h-3" />
                              {book.published_year}
                            </span>
                          )}
                        </div>

                        {/* Book Title & Info */}
                        <div className="px-5 space-y-2.5">
                          <h3 className="font-bold text-base text-slate-900 group-hover:text-indigo-600 transition-colors line-clamp-2 leading-snug">
                            {book.title}
                          </h3>

                          <div className="space-y-1 text-xs text-slate-600">
                            <p className="flex items-center gap-1.5 truncate">
                              <Users className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                              <span className="truncate">
                                {book.authors?.length > 0
                                  ? book.authors
                                      .map((a) => `${a.first_name} ${a.last_name}`)
                                      .join(', ')
                                  : 'Yazar Belirtilmemiş'}
                              </span>
                            </p>
                            <p className="flex items-center gap-1.5 truncate text-slate-500">
                              <Building2 className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                              <span className="truncate">
                                {book.publisher?.name || 'Yayınevi Belirtilmemiş'}
                              </span>
                            </p>
                          </div>

                          {/* Category Pills */}
                          {book.categories?.length > 0 && (
                            <div className="flex flex-wrap gap-1 pt-1">
                              {book.categories.map((cat) => (
                                <span
                                  key={cat.id}
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold bg-slate-100 text-slate-600"
                                >
                                  <Tag className="w-2.5 h-2.5 text-indigo-500" />
                                  {cat.name}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Card Footer CTA */}
                      <div className="p-5 pt-4 mt-4 border-t border-slate-100 flex items-center justify-between gap-2 bg-slate-50/40">
                        <span className="text-[11px] font-mono text-slate-400 truncate">
                          {book.isbn}
                        </span>
                        <span
                          className={`inline-flex items-center gap-1 text-xs font-bold px-3 py-1.5 rounded-xl transition-colors ${
                            inStock
                              ? 'bg-indigo-50 text-indigo-700 group-hover:bg-indigo-600 group-hover:text-white'
                              : 'bg-amber-50 text-amber-800 group-hover:bg-amber-600 group-hover:text-white'
                          }`}
                        >
                          {inStock ? 'İncele & Ödünç Al' : 'İncele & Rezerve Et'}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Pagination Controls */}
            {booksData.total_pages > 1 && (
              <div className="flex flex-wrap items-center justify-center gap-2 pt-4">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="inline-flex items-center gap-1 px-3.5 py-2 rounded-xl text-xs font-semibold bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 disabled:opacity-40 cursor-pointer"
                >
                  <ChevronLeft className="w-4 h-4" />
                  Önceki
                </button>

                {Array.from({ length: booksData.total_pages }, (_, idx) => idx + 1).map(
                  (pNum) => (
                    <button
                      key={pNum}
                      onClick={() => setPage(pNum)}
                      className={`w-9 h-9 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                        pNum === page
                          ? 'bg-indigo-600 text-white shadow-xs'
                          : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      {pNum}
                    </button>
                  )
                )}

                <button
                  onClick={() =>
                    setPage((p) => Math.min(booksData.total_pages, p + 1))
                  }
                  disabled={page >= booksData.total_pages}
                  className="inline-flex items-center gap-1 px-3.5 py-2 rounded-xl text-xs font-semibold bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 disabled:opacity-40 cursor-pointer"
                >
                  Sonraki
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        )}

        {activeTab === 'mylibrary' && user && (
          <MyLibraryView
            notify={notify}
            onSelectBook={(b) => setSelectedBook(b)}
          />
        )}

        {activeTab === 'admin' && user?.roles?.includes('ADMIN') && (
          <AdminPanel
            notify={notify}
            onCatalogChanged={() => {
              fetchFilterMetadata();
              fetchBooks();
            }}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200/80 py-5 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-slate-400">
          <span>
            © {new Date().getFullYear()} Kütüphane Yönetim Sistemi — FastAPI & React + Tailwind CSS
          </span>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="text-indigo-600 hover:underline font-medium"
          >
            Swagger API Dokümantasyonu (/docs) →
          </a>
        </div>
      </footer>

      {/* Auth Modal */}
      {authModalMode && (
        <AuthModal
          initialMode={authModalMode}
          onClose={() => setAuthModalMode(null)}
          onSuccess={(loggedInUser) => setUser(loggedInUser)}
          notify={notify}
        />
      )}

      {/* Book Detail Modal */}
      {selectedBook && (
        <BookDetailModal
          book={selectedBook}
          user={user}
          onClose={() => setSelectedBook(null)}
          onOpenAuth={(mode) => setAuthModalMode(mode)}
          onBookUpdated={() => fetchBooks()}
          notify={notify}
        />
      )}
    </div>
  );
}

