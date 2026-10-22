import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  BookOpen,
  Users,
  Tag,
  Building2,
  Plus,
  Pencil,
  Trash2,
  X,
  Check,
  RefreshCw,
} from 'lucide-react';
import { api } from '../api';

export default function AdminPanel({ notify, onCatalogChanged }) {
  const [subTab, setSubTab] = useState('books');
  const [loading, setLoading] = useState(true);

  const [books, setBooks] = useState([]);
  const [authors, setAuthors] = useState([]);
  const [categories, setCategories] = useState([]);
  const [publishers, setPublishers] = useState([]);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [modalType, setModalType] = useState('book'); // 'book' | 'author' | 'category' | 'publisher'
  const [editingItem, setEditingItem] = useState(null);
  const [saving, setSaving] = useState(false);

  // Forms
  const [bookForm, setBookForm] = useState({
    title: '',
    isbn: '',
    published_year: 2024,
    stock_count: 1,
    publisher_id: '',
    author_ids: [],
    category_ids: [],
  });

  const [authorForm, setAuthorForm] = useState({ first_name: '', last_name: '' });
  const [categoryForm, setCategoryForm] = useState({ name: '' });
  const [publisherForm, setPublisherForm] = useState({ name: '', contact_info: '' });

  const loadAllCatalogData = async () => {
    setLoading(true);
    try {
      const [booksRes, authorsRes, categoriesRes, publishersRes] = await Promise.all([
        api.getBooks({ page: 1, limit: 100 }),
        api.getAuthors(),
        api.getCategories(),
        api.getPublishers(),
      ]);
      setBooks(booksRes?.items || []);
      setAuthors(authorsRes || []);
      setCategories(categoriesRes || []);
      setPublishers(publishersRes || []);
    } catch (err) {
      notify(err.message || 'Katalog verileri yüklenemedi', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAllCatalogData();
  }, []);

  // Open Modals
  const openCreateModal = (type) => {
    setEditingItem(null);
    setModalType(type);
    if (type === 'book') {
      setBookForm({
        title: '',
        isbn: '',
        published_year: new Date().getFullYear(),
        stock_count: 1,
        publisher_id: publishers[0]?.id || '',
        author_ids: [],
        category_ids: [],
      });
    } else if (type === 'author') {
      setAuthorForm({ first_name: '', last_name: '' });
    } else if (type === 'category') {
      setCategoryForm({ name: '' });
    } else if (type === 'publisher') {
      setPublisherForm({ name: '', contact_info: '' });
    }
    setModalOpen(true);
  };

  const openEditModal = (type, item) => {
    setEditingItem(item);
    setModalType(type);
    if (type === 'book') {
      setBookForm({
        title: item.title || '',
        isbn: item.isbn || '',
        published_year: item.published_year || 2024,
        stock_count: item.stock_count ?? 0,
        publisher_id: item.publisher?.id || '',
        author_ids: (item.authors || []).map((a) => a.id),
        category_ids: (item.categories || []).map((c) => c.id),
      });
    } else if (type === 'author') {
      setAuthorForm({ first_name: item.first_name || '', last_name: item.last_name || '' });
    } else if (type === 'category') {
      setCategoryForm({ name: item.name || '' });
    } else if (type === 'publisher') {
      setPublisherForm({
        name: item.name || '',
        contact_info: item.contact_info || '',
      });
    }
    setModalOpen(true);
  };

  const toggleSelection = (list, id) => {
    return list.includes(id) ? list.filter((item) => item !== id) : [...list, id];
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      if (modalType === 'book') {
        const payload = {
          title: bookForm.title.trim(),
          isbn: bookForm.isbn.trim(),
          published_year: bookForm.published_year ? Number(bookForm.published_year) : null,
          stock_count: Number(bookForm.stock_count),
          publisher_id: bookForm.publisher_id || null,
          author_ids: bookForm.author_ids,
          category_ids: bookForm.category_ids,
        };
        if (editingItem) {
          await api.updateBook(editingItem.id, payload);
          notify('Kitap başarıyla güncellendi!', 'success');
        } else {
          await api.createBook(payload);
          notify('Yeni kitap kataloğa eklendi!', 'success');
        }
      } else if (modalType === 'author') {
        const payload = {
          first_name: authorForm.first_name.trim(),
          last_name: authorForm.last_name.trim(),
        };
        if (editingItem) {
          await api.updateAuthor(editingItem.id, payload);
          notify('Yazar bilgisi güncellendi!', 'success');
        } else {
          await api.createAuthor(payload);
          notify('Yeni yazar eklendi!', 'success');
        }
      } else if (modalType === 'category') {
        const payload = { name: categoryForm.name.trim() };
        if (editingItem) {
          await api.updateCategory(editingItem.id, payload);
          notify('Kategori güncellendi!', 'success');
        } else {
          await api.createCategory(payload);
          notify('Yeni kategori eklendi!', 'success');
        }
      } else if (modalType === 'publisher') {
        const payload = {
          name: publisherForm.name.trim(),
          contact_info: publisherForm.contact_info.trim() || null,
        };
        if (editingItem) {
          await api.updatePublisher(editingItem.id, payload);
          notify('Yayınevi güncellendi!', 'success');
        } else {
          await api.createPublisher(payload);
          notify('Yeni yayınevi eklendi!', 'success');
        }
      }

      setModalOpen(false);
      await loadAllCatalogData();
      if (onCatalogChanged) onCatalogChanged();
    } catch (err) {
      notify(err.message || 'Kayıt işlemi başarısız', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (type, item) => {
    const label =
      type === 'book'
        ? item.title
        : type === 'author'
        ? `${item.first_name} ${item.last_name}`
        : item.name;

    if (!window.confirm(`"${label}" kaydını silmek istediğinize emin misiniz?`)) {
      return;
    }

    try {
      if (type === 'book') await api.deleteBook(item.id);
      if (type === 'author') await api.deleteAuthor(item.id);
      if (type === 'category') await api.deleteCategory(item.id);
      if (type === 'publisher') await api.deletePublisher(item.id);

      notify(`"${label}" başarıyla silindi.`, 'success');
      await loadAllCatalogData();
      if (onCatalogChanged) onCatalogChanged();
    } catch (err) {
      notify(err.message || 'Silme işlemi başarısız (İlişkili ödünç kaydı olabilir)', 'error');
    }
  };

  return (
    <div className="space-y-6">
      {/* Admin Header Banner */}
      <div className="bg-gradient-to-r from-amber-500/10 via-orange-500/10 to-indigo-500/10 rounded-2xl p-5 sm:p-6 border border-amber-300/60 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-800 border border-amber-300 mb-2">
            <ShieldCheck className="w-3.5 h-3.5" />
            YETKİLİ YÖNETİCİ (ADMIN) MODÜLÜ
          </div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900">
            Katalog ve Envanter Yönetim Paneli
          </h1>
          <p className="text-xs sm:text-sm text-slate-600 mt-1">
            Kitap, Yazar, Kategori ve Yayınevi kayıtlarını çoklu ilişki desteğiyle ekleyebilir, düzenleyebilir ve silebilirsiniz.
          </p>
        </div>

        <button
          onClick={loadAllCatalogData}
          className="self-start sm:self-auto inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 shadow-2xs transition-colors cursor-pointer"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Verileri Yenile
        </button>
      </div>

      {/* Sub-tabs & Action Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 pb-3">
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setSubTab('books')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all cursor-pointer ${
              subTab === 'books'
                ? 'bg-slate-900 text-white shadow-xs'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            }`}
          >
            <BookOpen className="w-4 h-4" />
            Kitaplar ({books.length})
          </button>

          <button
            onClick={() => setSubTab('authors')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all cursor-pointer ${
              subTab === 'authors'
                ? 'bg-slate-900 text-white shadow-xs'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            }`}
          >
            <Users className="w-4 h-4" />
            Yazarlar ({authors.length})
          </button>

          <button
            onClick={() => setSubTab('categories')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all cursor-pointer ${
              subTab === 'categories'
                ? 'bg-slate-900 text-white shadow-xs'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            }`}
          >
            <Tag className="w-4 h-4" />
            Kategoriler ({categories.length})
          </button>

          <button
            onClick={() => setSubTab('publishers')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all cursor-pointer ${
              subTab === 'publishers'
                ? 'bg-slate-900 text-white shadow-xs'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            }`}
          >
            <Building2 className="w-4 h-4" />
            Yayınevleri ({publishers.length})
          </button>
        </div>

        <button
          onClick={() =>
            openCreateModal(
              subTab === 'books'
                ? 'book'
                : subTab === 'authors'
                ? 'author'
                : subTab === 'categories'
                ? 'category'
                : 'publisher'
            )
          }
          className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs sm:text-sm font-semibold shadow-sm shadow-indigo-200 transition-all cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          {subTab === 'books'
            ? 'Yeni Kitap Ekle'
            : subTab === 'authors'
            ? 'Yeni Yazar Ekle'
            : subTab === 'categories'
            ? 'Yeni Kategori Ekle'
            : 'Yeni Yayınevi Ekle'}
        </button>
      </div>

      {/* Responsive Tables (overflow-x-auto) */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xs overflow-hidden">
        <div className="overflow-x-auto">
          {subTab === 'books' && (
            <table className="w-full text-left border-collapse min-w-[720px]">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3.5 px-4">Kitap Başlığı</th>
                  <th className="py-3.5 px-4">ISBN</th>
                  <th className="py-3.5 px-4">Yazarlar</th>
                  <th className="py-3.5 px-4">Kategoriler</th>
                  <th className="py-3.5 px-4">Yayınevi / Yıl</th>
                  <th className="py-3.5 px-4">Stok</th>
                  <th className="py-3.5 px-4 text-right">İşlemler</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {books.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-slate-400 text-xs">
                      Henüz kitap eklenmemiş.
                    </td>
                  </tr>
                ) : (
                  books.map((b) => (
                    <tr key={b.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3.5 px-4 font-semibold text-slate-900">{b.title}</td>
                      <td className="py-3.5 px-4 text-xs font-mono text-slate-500">{b.isbn}</td>
                      <td className="py-3.5 px-4 text-xs text-slate-600">
                        {b.authors?.length > 0
                          ? b.authors.map((a) => `${a.first_name} ${a.last_name}`).join(', ')
                          : '-'}
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="flex flex-wrap gap-1">
                          {b.categories?.map((c) => (
                            <span
                              key={c.id}
                              className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-indigo-50 text-indigo-700"
                            >
                              {c.name}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-xs text-slate-600">
                        {b.publisher?.name || '-'} ({b.published_year || '-'})
                      </td>
                      <td className="py-3.5 px-4">
                        <span
                          className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-bold ${
                            b.stock_count > 0
                              ? 'bg-emerald-100 text-emerald-800'
                              : 'bg-rose-100 text-rose-800'
                          }`}
                        >
                          {b.stock_count} Adet
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-right space-x-1.5">
                        <button
                          onClick={() => openEditModal('book', b)}
                          className="p-1.5 rounded-lg text-indigo-600 hover:bg-indigo-50 transition-colors cursor-pointer"
                          title="Düzenle"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete('book', b)}
                          className="p-1.5 rounded-lg text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
                          title="Sil"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}

          {subTab === 'authors' && (
            <table className="w-full text-left border-collapse min-w-[480px]">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3.5 px-4">Ad</th>
                  <th className="py-3.5 px-4">Soyad</th>
                  <th className="py-3.5 px-4">UUID</th>
                  <th className="py-3.5 px-4 text-right">İşlemler</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {authors.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-8 text-center text-slate-400 text-xs">
                      Henüz yazar eklenmemiş.
                    </td>
                  </tr>
                ) : (
                  authors.map((a) => (
                    <tr key={a.id} className="hover:bg-slate-50/80">
                      <td className="py-3.5 px-4 font-semibold text-slate-900">{a.first_name}</td>
                      <td className="py-3.5 px-4 font-semibold text-slate-900">{a.last_name}</td>
                      <td className="py-3.5 px-4 text-xs font-mono text-slate-400">{a.id}</td>
                      <td className="py-3.5 px-4 text-right space-x-1.5">
                        <button
                          onClick={() => openEditModal('author', a)}
                          className="p-1.5 rounded-lg text-indigo-600 hover:bg-indigo-50 cursor-pointer"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete('author', a)}
                          className="p-1.5 rounded-lg text-rose-600 hover:bg-rose-50 cursor-pointer"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}

          {subTab === 'categories' && (
            <table className="w-full text-left border-collapse min-w-[420px]">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3.5 px-4">ID</th>
                  <th className="py-3.5 px-4">Kategori Adı</th>
                  <th className="py-3.5 px-4 text-right">İşlemler</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {categories.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="py-8 text-center text-slate-400 text-xs">
                      Henüz kategori eklenmemiş.
                    </td>
                  </tr>
                ) : (
                  categories.map((c) => (
                    <tr key={c.id} className="hover:bg-slate-50/80">
                      <td className="py-3.5 px-4 text-xs font-mono text-slate-500">#{c.id}</td>
                      <td className="py-3.5 px-4 font-semibold text-slate-900">{c.name}</td>
                      <td className="py-3.5 px-4 text-right space-x-1.5">
                        <button
                          onClick={() => openEditModal('category', c)}
                          className="p-1.5 rounded-lg text-indigo-600 hover:bg-indigo-50 cursor-pointer"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete('category', c)}
                          className="p-1.5 rounded-lg text-rose-600 hover:bg-rose-50 cursor-pointer"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}

          {subTab === 'publishers' && (
            <table className="w-full text-left border-collapse min-w-[520px]">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3.5 px-4">Yayınevi Adı</th>
                  <th className="py-3.5 px-4">İletişim Bilgisi</th>
                  <th className="py-3.5 px-4 text-right">İşlemler</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {publishers.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="py-8 text-center text-slate-400 text-xs">
                      Henüz yayınevi eklenmemiş.
                    </td>
                  </tr>
                ) : (
                  publishers.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-50/80">
                      <td className="py-3.5 px-4 font-semibold text-slate-900">{p.name}</td>
                      <td className="py-3.5 px-4 text-xs text-slate-600">
                        {p.contact_info || '-'}
                      </td>
                      <td className="py-3.5 px-4 text-right space-x-1.5">
                        <button
                          onClick={() => openEditModal('publisher', p)}
                          className="p-1.5 rounded-lg text-indigo-600 hover:bg-indigo-50 cursor-pointer"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete('publisher', p)}
                          className="p-1.5 rounded-lg text-rose-600 hover:bg-rose-50 cursor-pointer"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Create / Edit Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-lg max-h-[90vh] flex flex-col overflow-hidden my-auto">
            <div className="px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <h3 className="font-bold text-slate-900">
                {editingItem ? 'Kaydı Düzenle' : 'Yeni Kayıt Oluştur'} (
                {modalType === 'book'
                  ? 'Kitap'
                  : modalType === 'author'
                  ? 'Yazar'
                  : modalType === 'category'
                  ? 'Kategori'
                  : 'Yayınevi'}
                )
              </h3>
              <button
                onClick={() => setModalOpen(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/60"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSave} className="p-6 overflow-y-auto space-y-4">
              {modalType === 'book' && (
                <>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Kitap Başlığı *
                    </label>
                    <input
                      type="text"
                      required
                      value={bookForm.title}
                      onChange={(e) => setBookForm({ ...bookForm, title: e.target.value })}
                      placeholder="Örn: Suç ve Ceza"
                      className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        ISBN (10-17 krk) *
                      </label>
                      <input
                        type="text"
                        required
                        minLength={10}
                        maxLength={17}
                        value={bookForm.isbn}
                        onChange={(e) => setBookForm({ ...bookForm, isbn: e.target.value })}
                        placeholder="978-975-05-0001"
                        className="w-full px-3 py-2 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Yayın Yılı
                      </label>
                      <input
                        type="number"
                        value={bookForm.published_year}
                        onChange={(e) =>
                          setBookForm({ ...bookForm, published_year: e.target.value })
                        }
                        className="w-full px-3 py-2 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Stok Adedi (&ge; 0) *
                      </label>
                      <input
                        type="number"
                        required
                        min={0}
                        value={bookForm.stock_count}
                        onChange={(e) =>
                          setBookForm({ ...bookForm, stock_count: e.target.value })
                        }
                        className="w-full px-3 py-2 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Yayınevi Seçimi
                    </label>
                    <select
                      value={bookForm.publisher_id}
                      onChange={(e) =>
                        setBookForm({ ...bookForm, publisher_id: e.target.value })
                      }
                      className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    >
                      <option value="">-- Yayınevi Seçin (Opsiyonel) --</option>
                      {publishers.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Multi-select Authors */}
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Yazarlar (Çoklu Seçim - BookAuthors)
                    </label>
                    {authors.length === 0 ? (
                      <p className="text-xs text-slate-400">
                        Önce "Yazarlar" sekmesinden yazar ekleyebilirsiniz.
                      </p>
                    ) : (
                      <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                        {authors.map((a) => {
                          const selected = bookForm.author_ids.includes(a.id);
                          return (
                            <button
                              key={a.id}
                              type="button"
                              onClick={() =>
                                setBookForm({
                                  ...bookForm,
                                  author_ids: toggleSelection(bookForm.author_ids, a.id),
                                })
                              }
                              className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                                selected
                                  ? 'bg-indigo-600 text-white shadow-2xs'
                                  : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-100'
                              }`}
                            >
                              {selected && <Check className="w-3 h-3" />}
                              {a.first_name} {a.last_name}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  {/* Multi-select Categories */}
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Kategoriler (Çoklu Seçim - BookCategories)
                    </label>
                    {categories.length === 0 ? (
                      <p className="text-xs text-slate-400">
                        Önce "Kategoriler" sekmesinden kategori ekleyebilirsiniz.
                      </p>
                    ) : (
                      <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                        {categories.map((c) => {
                          const selected = bookForm.category_ids.includes(c.id);
                          return (
                            <button
                              key={c.id}
                              type="button"
                              onClick={() =>
                                setBookForm({
                                  ...bookForm,
                                  category_ids: toggleSelection(bookForm.category_ids, c.id),
                                })
                              }
                              className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                                selected
                                  ? 'bg-indigo-600 text-white shadow-2xs'
                                  : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-100'
                              }`}
                            >
                              {selected && <Check className="w-3 h-3" />}
                              {c.name}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </>
              )}

              {modalType === 'author' && (
                <>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Yazar Adı *
                    </label>
                    <input
                      type="text"
                      required
                      value={authorForm.first_name}
                      onChange={(e) =>
                        setAuthorForm({ ...authorForm, first_name: e.target.value })
                      }
                      placeholder="Örn: Fyodor"
                      className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Yazar Soyadı *
                    </label>
                    <input
                      type="text"
                      required
                      value={authorForm.last_name}
                      onChange={(e) =>
                        setAuthorForm({ ...authorForm, last_name: e.target.value })
                      }
                      placeholder="Örn: Dostoyevski"
                      className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                </>
              )}

              {modalType === 'category' && (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Kategori Adı (Benzersiz) *
                  </label>
                  <input
                    type="text"
                    required
                    value={categoryForm.name}
                    onChange={(e) => setCategoryForm({ name: e.target.value })}
                    placeholder="Örn: Dünya Klasikleri"
                    className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              )}

              {modalType === 'publisher' && (
                <>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Yayınevi Adı *
                    </label>
                    <input
                      type="text"
                      required
                      value={publisherForm.name}
                      onChange={(e) =>
                        setPublisherForm({ ...publisherForm, name: e.target.value })
                      }
                      placeholder="Örn: İş Bankası Kültür Yayınları"
                      className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      İletişim Bilgisi
                    </label>
                    <input
                      type="text"
                      value={publisherForm.contact_info}
                      onChange={(e) =>
                        setPublisherForm({ ...publisherForm, contact_info: e.target.value })
                      }
                      placeholder="Örn: info@iskultur.com.tr"
                      className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                </>
              )}

              <div className="pt-3 flex items-center justify-end gap-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100"
                >
                  İptal
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-5 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white shadow-xs cursor-pointer"
                >
                  {saving ? 'Kaydediliyor...' : editingItem ? 'Güncelle' : 'Kaydet'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

