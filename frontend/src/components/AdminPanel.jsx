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
  Search,
  Sparkles,
  Clock,
  AlertTriangle,
  CheckCircle2,
  FastForward,
  Image as ImageIcon,
  Receipt,
  ScrollText,
  DollarSign,
  Filter,
  AlertCircle,
  Info,
} from 'lucide-react';
import { api } from '../api';

export default function AdminPanel({ notify, onCatalogChanged }) {
  const [subTab, setSubTab] = useState('books');
  const [loading, setLoading] = useState(true);

  const [books, setBooks] = useState([]);
  const [authors, setAuthors] = useState([]);
  const [categories, setCategories] = useState([]);
  const [publishers, setPublishers] = useState([]);
  const [borrowings, setBorrowings] = useState([]);
  const [simulatingId, setSimulatingId] = useState(null);

  // Ödenmemiş Borçlar State'leri
  const [unpaidPenalties, setUnpaidPenalties] = useState({
    total_unpaid_amount: 0,
    debtor_count: 0,
    items: [],
  });
  const [collectingId, setCollectingId] = useState(null);
  const [penaltyStatusFilter, setPenaltyStatusFilter] = useState('ALL');

  // Sistem Logları State'leri
  const [systemLogs, setSystemLogs] = useState([]);
  const [logCategoryFilter, setLogCategoryFilter] = useState('');
  const [logLevelFilter, setLogLevelFilter] = useState('');
  const [logsLoading, setLogsLoading] = useState(false);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [modalType, setModalType] = useState('book'); // 'book' | 'author' | 'category' | 'publisher'
  const [editingItem, setEditingItem] = useState(null);
  const [saving, setSaving] = useState(false);

  // Inline search & create states inside Book Modal
  const [publisherQuery, setPublisherQuery] = useState('');
  const [authorQuery, setAuthorQuery] = useState('');
  const [categoryQuery, setCategoryQuery] = useState('');
  const [inlineCreating, setInlineCreating] = useState(false);

  // ISBN lookup states
  const [lookupIsbn, setLookupIsbn] = useState('');
  const [lookupLoading, setLookupLoading] = useState(false);

  // Forms
  const [bookForm, setBookForm] = useState({
    title: '',
    isbn: '',
    published_year: 2024,
    stock_count: 1,
    publisher_id: '',
    author_ids: [],
    category_ids: [],
    cover_url: '',
  });

  const [authorForm, setAuthorForm] = useState({ first_name: '', last_name: '' });
  const [categoryForm, setCategoryForm] = useState({ name: '' });
  const [publisherForm, setPublisherForm] = useState({ name: '', contact_info: '' });

  const loadAllCatalogData = async () => {
    setLoading(true);
    try {
      const [booksRes, authorsRes, categoriesRes, publishersRes, borrowingsRes, penaltiesRes] =
        await Promise.all([
          api.getBooks({ page: 1, limit: 100 }),
          api.getAuthors(),
          api.getCategories(),
          api.getPublishers(),
          api.getAdminBorrowings().catch(() => []),
          api.getUnpaidPenalties().catch(() => ({ total_unpaid_amount: 0, debtor_count: 0, items: [] })),
        ]);
      setBooks(booksRes?.items || []);
      setAuthors(authorsRes || []);
      setCategories(categoriesRes || []);
      setPublishers(publishersRes || []);
      setBorrowings(borrowingsRes || []);
      setUnpaidPenalties(penaltiesRes || { total_unpaid_amount: 0, debtor_count: 0, items: [] });
    } catch (err) {
      notify(err.message || 'Katalog verileri yüklenemedi', 'error');
    } finally {
      setLoading(false);
    }
  };

  const loadSystemLogs = async (category = logCategoryFilter, level = logLevelFilter) => {
    setLogsLoading(true);
    try {
      const logs = await api.getSystemLogs({
        category: category || undefined,
        level: level || undefined,
        limit: 100,
      });
      setSystemLogs(logs || []);
    } catch (err) {
      notify(err.message || 'Sistem logları yüklenemedi', 'error');
    } finally {
      setLogsLoading(false);
    }
  };

  const handleSimulateOverdue = async (borrowingId) => {
    setSimulatingId(borrowingId);
    try {
      const updated = await api.simulateOverdue(borrowingId);
      notify(
        `Gecikme simülasyonu uygulandı! Son teslim tarihi 5 gün geri çekildi (${updated.due_date}) ve durum OVERDUE (${updated.penalty_amount} TL) yapıldı.`,
        'success'
      );
      await loadAllCatalogData();
    } catch (err) {
      notify(err.message || 'Gecikme simülasyonu başarısız', 'error');
    } finally {
      setSimulatingId(null);
    }
  };

  // Elden Ceza Tahsilatı (Admin yetkisiyle borç kapatma)
  const handleCollectPenalty = async (item) => {
    const amountStr = Number(item.penalty_amount || 0).toFixed(2);
    if (
      !window.confirm(
        `"${item.user_full_name}" adlı kullanıcının ${amountStr} TL tutarındaki gecikme cezası elden tahsil edildi olarak işaretlenecek ve borç kapatılacaktır.\n\nOnaylıyor musunuz?`
      )
    ) {
      return;
    }

    setCollectingId(item.borrowing_id);
    try {
      await api.payPenalty(item.borrowing_id);
      notify(
        `"${item.user_full_name}" kullanıcısının ${amountStr} TL cezası başarıyla tahsil edildi ve borç kapatıldı!`,
        'success'
      );
      await loadAllCatalogData();
      if (subTab === 'logs') {
        await loadSystemLogs();
      }
    } catch (err) {
      notify(err.message || 'Ceza tahsil edilirken hata oluştu', 'error');
    } finally {
      setCollectingId(null);
    }
  };

  const handleCategoryFilterChange = (cat) => {
    setLogCategoryFilter(cat);
    loadSystemLogs(cat, logLevelFilter);
  };

  const handleLevelFilterChange = (lvl) => {
    setLogLevelFilter(lvl);
    loadSystemLogs(logCategoryFilter, lvl);
  };

  const formatTimestamp = (ts) => {
    if (!ts) return '-';
    try {
      const d = new Date(ts);
      if (!isNaN(d.getTime())) {
        return d.toLocaleString('tr-TR', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        });
      }
    } catch {
      // fallback
    }
    return String(ts).replace('T', ' ').slice(0, 19);
  };

  const getLevelBadge = (level) => {
    switch (level?.toUpperCase()) {
      case 'ERROR':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300">
            <AlertCircle className="w-3 h-3 text-rose-600" />
            ERROR
          </span>
        );
      case 'WARNING':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-300">
            <AlertTriangle className="w-3 h-3 text-amber-600" />
            WARNING
          </span>
        );
      case 'INFO':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            INFO
          </span>
        );
    }
  };

  const getCategoryBadge = (category) => {
    const cat = category?.toUpperCase() || 'SYSTEM';
    const colorMap = {
      AUTH: 'bg-indigo-100 text-indigo-800 border-indigo-200',
      BORROWING: 'bg-sky-100 text-sky-800 border-sky-200',
      RESERVATION: 'bg-purple-100 text-purple-800 border-purple-200',
      PENALTY: 'bg-rose-100 text-rose-800 border-rose-200',
      REVIEW: 'bg-amber-100 text-amber-800 border-amber-200',
      CATALOG: 'bg-teal-100 text-teal-800 border-teal-200',
      SYSTEM: 'bg-slate-100 text-slate-800 border-slate-200',
    };
    const color = colorMap[cat] || colorMap.SYSTEM;
    return (
      <span
        className={`inline-block px-2.5 py-0.5 rounded-md text-[11px] font-bold border ${color}`}
      >
        {cat}
      </span>
    );
  };

  useEffect(() => {
    loadAllCatalogData();
  }, []);

  useEffect(() => {
    if (subTab === 'logs') {
      loadSystemLogs(logCategoryFilter, logLevelFilter);
    } else if (subTab === 'penalties') {
      api
        .getUnpaidPenalties()
        .then((res) =>
          setUnpaidPenalties(
            res || { total_unpaid_amount: 0, debtor_count: 0, items: [] }
          )
        )
        .catch(() => {});
    }
  }, [subTab]);

  // Open Modals
  const openCreateModal = (type) => {
    setEditingItem(null);
    setModalType(type);
    setPublisherQuery('');
    setAuthorQuery('');
    setCategoryQuery('');
    setLookupIsbn('');

    if (type === 'book') {
      setBookForm({
        title: '',
        isbn: '',
        published_year: new Date().getFullYear(),
        stock_count: 1,
        publisher_id: publishers[0]?.id || '',
        author_ids: [],
        category_ids: [],
        cover_url: '',
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
    setPublisherQuery('');
    setAuthorQuery('');
    setCategoryQuery('');
    setLookupIsbn(item?.isbn || '');

    if (type === 'book') {
      setBookForm({
        title: item.title || '',
        isbn: item.isbn || '',
        published_year: item.published_year || 2024,
        stock_count: item.stock_count ?? 0,
        publisher_id: item.publisher?.id || '',
        author_ids: (item.authors || []).map((a) => a.id),
        category_ids: (item.categories || []).map((c) => c.id),
        cover_url: item.cover_url || '',
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

  // Yardımcı: Tam adı (Örn: "Ahmet Hamdi Tanpınar") ad ve soyad olarak ayırır
  const splitFullName = (fullName) => {
    const parts = fullName.trim().split(/\s+/);
    if (parts.length === 1) {
      return { first_name: parts[0], last_name: '-' };
    }
    const last_name = parts.pop();
    const first_name = parts.join(' ');
    return { first_name, last_name };
  };

  // Kitap modalı içinden anında yeni Yayınevi oluştur ve seç
  const handleQuickCreatePublisher = async (rawName) => {
    const name = rawName.trim();
    if (!name) return null;

    // Zaten varsa mevcut olanı seç
    const existing = publishers.find(
      (p) => p.name.toLowerCase() === name.toLowerCase()
    );
    if (existing) {
      setBookForm((prev) => ({ ...prev, publisher_id: existing.id }));
      setPublisherQuery('');
      return existing.id;
    }

    setInlineCreating(true);
    try {
      const created = await api.createPublisher({ name, contact_info: null });
      setPublishers((prev) => [...prev, created]);
      setBookForm((prev) => ({ ...prev, publisher_id: created.id }));
      setPublisherQuery('');
      notify(`"${created.name}" yayınevleri arasına eklendi ve seçildi!`, 'success');
      if (onCatalogChanged) onCatalogChanged();
      return created.id;
    } catch (err) {
      notify(err.message || 'Yayınevi oluşturulamadı', 'error');
      return null;
    } finally {
      setInlineCreating(false);
    }
  };

  // Kitap modalı içinden anında yeni Yazar oluştur ve seç
  const handleQuickCreateAuthor = async (rawFullName) => {
    const cleaned = rawFullName.trim();
    if (!cleaned) return null;

    // Zaten varsa mevcut olanı seç
    const existing = authors.find(
      (a) => `${a.first_name} ${a.last_name}`.toLowerCase() === cleaned.toLowerCase()
    );
    if (existing) {
      setBookForm((prev) => ({
        ...prev,
        author_ids: prev.author_ids.includes(existing.id)
          ? prev.author_ids
          : [...prev.author_ids, existing.id],
      }));
      setAuthorQuery('');
      return existing.id;
    }

    setInlineCreating(true);
    try {
      const { first_name, last_name } = splitFullName(cleaned);
      const created = await api.createAuthor({ first_name, last_name });
      setAuthors((prev) => [...prev, created]);
      setBookForm((prev) => ({
        ...prev,
        author_ids: [...prev.author_ids, created.id],
      }));
      setAuthorQuery('');
      notify(
        `"${created.first_name} ${created.last_name}" yazarlar arasına eklendi ve seçildi!`,
        'success'
      );
      if (onCatalogChanged) onCatalogChanged();
      return created.id;
    } catch (err) {
      notify(err.message || 'Yazar oluşturulamadı', 'error');
      return null;
    } finally {
      setInlineCreating(false);
    }
  };

  // Kitap modalı içinden anında yeni Kategori oluştur ve seç
  const handleQuickCreateCategory = async (rawName) => {
    const name = rawName.trim();
    if (!name) return null;

    const existing = categories.find(
      (c) => c.name.toLowerCase() === name.toLowerCase()
    );
    if (existing) {
      setBookForm((prev) => ({
        ...prev,
        category_ids: prev.category_ids.includes(existing.id)
          ? prev.category_ids
          : [...prev.category_ids, existing.id],
      }));
      setCategoryQuery('');
      return existing.id;
    }

    setInlineCreating(true);
    try {
      const created = await api.createCategory({ name });
      setCategories((prev) => [...prev, created]);
      setBookForm((prev) => ({
        ...prev,
        category_ids: [...prev.category_ids, created.id],
      }));
      setCategoryQuery('');
      notify(`"${created.name}" kategoriler arasına eklendi ve seçildi!`, 'success');
      if (onCatalogChanged) onCatalogChanged();
      return created.id;
    } catch (err) {
      notify(err.message || 'Kategori oluşturulamadı', 'error');
      return null;
    } finally {
      setInlineCreating(false);
    }
  };

  const handleLookupIsbn = async (isbnToLookup) => {
    const queryIsbn = (isbnToLookup || lookupIsbn || bookForm.isbn).trim();
    if (!queryIsbn) {
      notify('Lütfen sorgulanacak ISBN numarasını girin.', 'error');
      return;
    }
    setLookupLoading(true);
    try {
      const data = await api.lookupIsbn(queryIsbn);
      setBookForm((prev) => ({
        ...prev,
        title: data.title || prev.title,
        isbn: data.isbn || prev.isbn,
        published_year: data.published_year ?? prev.published_year,
        cover_url: data.cover_url || prev.cover_url,
        publisher_id: data.publisher_id || prev.publisher_id,
        author_ids: data.author_ids?.length ? data.author_ids : prev.author_ids,
        category_ids: data.category_ids?.length ? data.category_ids : prev.category_ids,
      }));
      setLookupIsbn(data.isbn || queryIsbn);
      // Yeni yazar, yayınevi veya kategoriler veritabanında oluşturulduğundan listeleri güncelle
      await loadAllCatalogData();
      notify(
        `"${data.title}" kitap bilgileri ISBN üzerinden başarıyla çekildi!`,
        'success'
      );
    } catch (err) {
      notify(err.message || 'Bu ISBN ile kitap bulunamadı', 'error');
    } finally {
      setLookupLoading(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      if (modalType === 'book') {
        let finalPublisherId = bookForm.publisher_id || null;
        let finalAuthorIds = [...bookForm.author_ids];
        let finalCategoryIds = [...bookForm.category_ids];

        // Kullanıcı arama kutularına yeni bir isim yazıp '+' butonuna basmadan direkt Kaydet'e bastıysa otomatik oluştur!
        if (publisherQuery.trim()) {
          const newPubId = await handleQuickCreatePublisher(publisherQuery);
          if (newPubId) finalPublisherId = newPubId;
        }
        if (authorQuery.trim()) {
          const newAuthId = await handleQuickCreateAuthor(authorQuery);
          if (newAuthId && !finalAuthorIds.includes(newAuthId)) {
            finalAuthorIds.push(newAuthId);
          }
        }
        if (categoryQuery.trim()) {
          const newCatId = await handleQuickCreateCategory(categoryQuery);
          if (newCatId && !finalCategoryIds.includes(newCatId)) {
            finalCategoryIds.push(newCatId);
          }
        }

        const payload = {
          title: bookForm.title.trim(),
          isbn: bookForm.isbn.trim(),
          published_year: bookForm.published_year ? Number(bookForm.published_year) : null,
          stock_count: Number(bookForm.stock_count),
          cover_url: bookForm.cover_url ? bookForm.cover_url.trim() : null,
          publisher_id: finalPublisherId,
          author_ids: finalAuthorIds,
          category_ids: finalCategoryIds,
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

  // Filtered lists for Book Modal
  const filteredPublishers = publishers.filter((p) =>
    p.name.toLowerCase().includes(publisherQuery.trim().toLowerCase())
  );
  const exactPublisherExists = publishers.some(
    (p) => p.name.toLowerCase() === publisherQuery.trim().toLowerCase()
  );
  const selectedPublisherObj = publishers.find((p) => p.id === bookForm.publisher_id);

  const filteredAuthors = authors.filter((a) =>
    `${a.first_name} ${a.last_name}`
      .toLowerCase()
      .includes(authorQuery.trim().toLowerCase())
  );
  const exactAuthorExists = authors.some(
    (a) =>
      `${a.first_name} ${a.last_name}`.toLowerCase() ===
      authorQuery.trim().toLowerCase()
  );

  const filteredCategories = categories.filter((c) =>
    c.name.toLowerCase().includes(categoryQuery.trim().toLowerCase())
  );
  const exactCategoryExists = categories.some(
    (c) => c.name.toLowerCase() === categoryQuery.trim().toLowerCase()
  );

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
            Kitap eklerken mevcut Yazar, Kategori ve Yayınevlerini arayarak seçebilir; listede yoksa adını yazarak anında oluşturabilirsiniz.
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

          <button
            onClick={() => setSubTab('borrowings')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all cursor-pointer ${
              subTab === 'borrowings'
                ? 'bg-rose-600 text-white shadow-xs'
                : 'bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100'
            }`}
          >
            <Clock className="w-4 h-4" />
            Ödünç İşlemleri & Gecikme Simülasyonu ({borrowings.length})
          </button>

          <button
            onClick={() => setSubTab('penalties')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all cursor-pointer ${
              subTab === 'penalties'
                ? 'bg-amber-600 text-white shadow-xs'
                : 'bg-amber-50 text-amber-800 border border-amber-200 hover:bg-amber-100'
            }`}
          >
            <Receipt className="w-4 h-4" />
            Ödenmemiş Borçlar ({unpaidPenalties?.debtor_count ?? 0})
          </button>

          <button
            onClick={() => setSubTab('logs')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all cursor-pointer ${
              subTab === 'logs'
                ? 'bg-indigo-600 text-white shadow-xs'
                : 'bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100'
            }`}
          >
            <ScrollText className="w-4 h-4" />
            Sistem Logları ({systemLogs.length})
          </button>
        </div>

        {!['borrowings', 'penalties', 'logs'].includes(subTab) && (
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
        )}
      </div>

      {/* Ödenmemiş Borçlar KPI Özet Kartları (subTab === 'penalties') */}
      {subTab === 'penalties' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="p-4 rounded-2xl bg-gradient-to-br from-rose-50 to-red-100/70 border border-rose-200 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-rose-700 uppercase tracking-wider">
                  Tahsil Edilmemiş Borç
                </span>
                <Receipt className="w-5 h-5 text-rose-600" />
              </div>
              <div className="text-2xl font-extrabold text-rose-900 mt-2">
                {Number(unpaidPenalties?.total_unpaid_amount || 0).toFixed(2)} TL
              </div>
              <p className="text-[11px] text-rose-600/90 mt-1">
                Kütüphaneye olan tüm açık borç tutarı
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-gradient-to-br from-amber-50 to-orange-100/70 border border-amber-200 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-amber-700 uppercase tracking-wider">
                  Borçlu Kayıt Sayısı
                </span>
                <Users className="w-5 h-5 text-amber-600" />
              </div>
              <div className="text-2xl font-extrabold text-amber-900 mt-2">
                {unpaidPenalties?.debtor_count || 0} Adet
              </div>
              <p className="text-[11px] text-amber-700/90 mt-1">
                Ceza borcu bulunan toplam ödünç kaydı
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-gradient-to-br from-red-50 to-rose-50 border border-red-200 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-red-700 uppercase tracking-wider">
                  Aktif Gecikmede Olanlar
                </span>
                <AlertTriangle className="w-5 h-5 text-red-600" />
              </div>
              <div className="text-2xl font-extrabold text-red-900 mt-2">
                {(unpaidPenalties?.items || []).filter((i) => i.status === 'OVERDUE').length} Kayıt
              </div>
              <p className="text-[11px] text-red-600/90 mt-1">
                Teslim tarihi geçmiş aktif ödünçler
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-gradient-to-br from-slate-50 to-indigo-50 border border-slate-200 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-indigo-700 uppercase tracking-wider">
                  İade Edilmiş Borçlular
                </span>
                <Clock className="w-5 h-5 text-indigo-600" />
              </div>
              <div className="text-2xl font-extrabold text-indigo-900 mt-2">
                {(unpaidPenalties?.items || []).filter((i) => i.status === 'RETURNED').length} Kayıt
              </div>
              <p className="text-[11px] text-slate-600 mt-1">
                Kitabı teslim etmiş ancak cezayı ödememiş
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-1.5 bg-slate-100 p-1 rounded-xl">
              <button
                onClick={() => setPenaltyStatusFilter('ALL')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                  penaltyStatusFilter === 'ALL'
                    ? 'bg-white text-slate-900 shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Tümü ({(unpaidPenalties?.items || []).length})
              </button>
              <button
                onClick={() => setPenaltyStatusFilter('OVERDUE')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                  penaltyStatusFilter === 'OVERDUE'
                    ? 'bg-white text-rose-700 shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Aktif Gecikenler ({(unpaidPenalties?.items || []).filter((i) => i.status === 'OVERDUE').length})
              </button>
              <button
                onClick={() => setPenaltyStatusFilter('RETURNED')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                  penaltyStatusFilter === 'RETURNED'
                    ? 'bg-white text-amber-700 shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                İade Edilmiş ({(unpaidPenalties?.items || []).filter((i) => i.status === 'RETURNED').length})
              </button>
            </div>

            <button
              onClick={async () => {
                try {
                  const res = await api.getUnpaidPenalties();
                  setUnpaidPenalties(res || { total_unpaid_amount: 0, debtor_count: 0, items: [] });
                  notify('Borçlu kayıtları güncellendi.', 'success');
                } catch {
                  notify('Borçlu kayıtları güncellenemedi.', 'error');
                }
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 transition-colors cursor-pointer shadow-2xs"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Borçları Yenile
            </button>
          </div>
        </div>
      )}

      {/* Responsive Tables (overflow-x-auto) */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xs overflow-hidden">
        {/* Sistem Logları Filtre ve Yenileme Çubuğu */}
        {subTab === 'logs' && (
          <div className="p-4 bg-slate-50 border-b border-slate-200 flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2.5">
              <div className="flex items-center gap-1.5">
                <Filter className="w-4 h-4 text-slate-500" />
                <span className="text-xs font-bold text-slate-700">Filtrele:</span>
              </div>

              {/* Kategori Filtresi */}
              <select
                value={logCategoryFilter}
                onChange={(e) => handleCategoryFilterChange(e.target.value)}
                className="px-3 py-1.5 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
              >
                <option value="">Tüm Kategoriler</option>
                <option value="AUTH">AUTH (Giriş / Kayıt)</option>
                <option value="BORROWING">BORROWING (Ödünç / İade)</option>
                <option value="RESERVATION">RESERVATION (Rezervasyon)</option>
                <option value="PENALTY">PENALTY (Ceza & Tahsilat)</option>
                <option value="REVIEW">REVIEW (Yorum & Değerlendirme)</option>
                <option value="CATALOG">CATALOG (Katalog İşlemleri)</option>
                <option value="SYSTEM">SYSTEM (Sistem)</option>
              </select>

              {/* Seviye Filtresi */}
              <select
                value={logLevelFilter}
                onChange={(e) => handleLevelFilterChange(e.target.value)}
                className="px-3 py-1.5 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
              >
                <option value="">Tüm Seviyeler</option>
                <option value="INFO">INFO (Bilgi)</option>
                <option value="WARNING">WARNING (Uyarı)</option>
                <option value="ERROR">ERROR (Hata)</option>
              </select>

              {(logCategoryFilter || logLevelFilter) && (
                <button
                  onClick={() => {
                    setLogCategoryFilter('');
                    setLogLevelFilter('');
                    loadSystemLogs('', '');
                  }}
                  className="text-xs text-rose-600 hover:text-rose-800 font-semibold cursor-pointer underline ml-1"
                >
                  Filtreleri Temizle
                </button>
              )}
            </div>

            <div className="flex items-center gap-2.5">
              <span className="text-xs text-slate-500 font-medium">
                Son <strong>{systemLogs.length}</strong> işlem (Maks 100)
              </span>
              <button
                onClick={() => loadSystemLogs(logCategoryFilter, logLevelFilter)}
                disabled={logsLoading}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold border border-slate-200 shadow-2xs transition-colors cursor-pointer disabled:opacity-60"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${logsLoading ? 'animate-spin' : ''}`} />
                Logları Yenile
              </button>
            </div>
          </div>
        )}

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

          {subTab === 'borrowings' && (
            <table className="w-full text-left border-collapse min-w-[780px]">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3.5 px-4">Kullanıcı</th>
                  <th className="py-3.5 px-4">Kitap</th>
                  <th className="py-3.5 px-4">Ödünç / Son Teslim</th>
                  <th className="py-3.5 px-4">Durum & Gecikme</th>
                  <th className="py-3.5 px-4">Ceza Tutarı</th>
                  <th className="py-3.5 px-4 text-right">Canlı Sunum Test İşlemi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {borrowings.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-400 text-xs">
                      Henüz ödünç alma işlemi bulunmuyor.
                    </td>
                  </tr>
                ) : (
                  borrowings.map((item) => {
                    const isReturned = item.status === 'RETURNED';
                    const isOverdue = item.status === 'OVERDUE' || (item.overdue_days || 0) > 0;
                    const penalty = Number(item.penalty_amount || 0);

                    return (
                      <tr key={item.id} className="hover:bg-slate-50/80 transition-colors">
                        <td className="py-3.5 px-4">
                          <div className="font-semibold text-slate-900">
                            {item.user_full_name || 'Kullanıcı'}
                          </div>
                          <div className="text-xs text-slate-500">
                            {item.user_email || item.user_id}
                          </div>
                        </td>
                        <td className="py-3.5 px-4 font-semibold text-slate-800">
                          {item.book_title ||
                            books.find((b) => b.id === item.book_id)?.title ||
                            item.book_id}
                        </td>
                        <td className="py-3.5 px-4 text-xs text-slate-600 space-y-0.5">
                          <div>
                            <span className="text-slate-400">Alış: </span>
                            <span className="font-medium">{item.borrow_date}</span>
                          </div>
                          <div>
                            <span className="text-slate-400">Son Teslim: </span>
                            <span
                              className={`font-bold ${
                                !isReturned && isOverdue ? 'text-rose-600' : 'text-slate-800'
                              }`}
                            >
                              {item.due_date}
                            </span>
                          </div>
                          {item.return_date && (
                            <div>
                              <span className="text-emerald-600">İade: </span>
                              <span className="font-semibold text-emerald-700">
                                {item.return_date}
                              </span>
                            </div>
                          )}
                        </td>
                        <td className="py-3.5 px-4">
                          {isReturned ? (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-slate-100 text-slate-700 border border-slate-300">
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                              RETURNED (İade Edildi)
                            </span>
                          ) : isOverdue ? (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-extrabold bg-rose-600 text-white">
                              <AlertTriangle className="w-3.5 h-3.5" />
                              OVERDUE ({item.overdue_days} Gün Gecikti)
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                              <Clock className="w-3.5 h-3.5" />
                              ACTIVE
                            </span>
                          )}
                        </td>
                        <td className="py-3.5 px-4">
                          {penalty > 0 ? (
                            <div className="space-y-0.5">
                              <span className="font-extrabold text-rose-700 text-xs block">
                                {penalty.toFixed(2)} TL
                              </span>
                              <span
                                className={`inline-block px-2 py-0.5 rounded-md text-[10px] font-bold ${
                                  item.is_penalty_paid
                                    ? 'bg-emerald-100 text-emerald-800'
                                    : isReturned
                                    ? 'bg-rose-100 text-rose-800'
                                    : 'bg-amber-100 text-amber-800'
                                }`}
                              >
                                {item.is_penalty_paid
                                  ? 'Ödendi'
                                  : isReturned
                                  ? 'Ödenmedi'
                                  : 'Birikiyor (Aktif)'}
                              </span>
                            </div>
                          ) : (
                            <span className="text-xs text-slate-400">0.00 TL</span>
                          )}
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          {!isReturned ? (
                            <button
                              onClick={() => handleSimulateOverdue(item.id)}
                              disabled={simulatingId === item.id}
                              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 disabled:opacity-60 text-white text-xs font-bold shadow-2xs transition-colors cursor-pointer"
                            >
                              <FastForward className="w-3.5 h-3.5" />
                              {simulatingId === item.id
                                ? 'Simüle Ediliyor...'
                                : 'Gecikme Simüle Et (-5 Gün)'}
                            </button>
                          ) : (
                            <span className="text-xs text-slate-400 italic">
                              İade tamamlandı
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          )}

          {/* Ödenmemiş Borçlar Tablosu */}
          {subTab === 'penalties' && (
            <table className="w-full text-left border-collapse min-w-[840px]">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3.5 px-4">Borçlu Kullanıcı</th>
                  <th className="py-3.5 px-4">Kitap</th>
                  <th className="py-3.5 px-4">Ödünç / Teslim / İade</th>
                  <th className="py-3.5 px-4">Gecikme Durumu</th>
                  <th className="py-3.5 px-4">Borç Tutarı</th>
                  <th className="py-3.5 px-4 text-right">Tahsilat İşlemi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {filteredPenalties.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center">
                      <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 mb-2">
                        <CheckCircle2 className="w-6 h-6" />
                      </div>
                      <div className="text-sm font-bold text-slate-800">
                        Ödenmemiş ceza borcu bulunmuyor
                      </div>
                      <p className="text-xs text-slate-500 mt-1">
                        Tebrikler! Seçilen kriterlere uyan gecikmiş veya tahsil edilmemiş herhangi bir ceza borcu yoktur.
                      </p>
                    </td>
                  </tr>
                ) : (
                  filteredPenalties.map((item) => {
                    const isReturned = item.status === 'RETURNED';
                    const isCollecting = collectingId === item.borrowing_id;
                    const penalty = Number(item.penalty_amount || 0);

                    return (
                      <tr key={item.borrowing_id} className="hover:bg-slate-50/80 transition-colors">
                        <td className="py-3.5 px-4">
                          <div className="font-semibold text-slate-900">
                            {item.user_full_name}
                          </div>
                          <div className="text-xs text-slate-500">{item.user_email}</div>
                        </td>
                        <td className="py-3.5 px-4">
                          <div className="font-semibold text-slate-800">
                            {item.book_title}
                          </div>
                          <div className="text-[11px] font-mono text-slate-400">
                            ID: {item.book_id}
                          </div>
                        </td>
                        <td className="py-3.5 px-4 text-xs text-slate-600 space-y-0.5">
                          <div>
                            <span className="text-slate-400">Alış: </span>
                            <span className="font-medium">{item.borrow_date}</span>
                          </div>
                          <div>
                            <span className="text-slate-400">Son Teslim: </span>
                            <span className="font-bold text-rose-600">{item.due_date}</span>
                          </div>
                          {item.return_date && (
                            <div>
                              <span className="text-emerald-600">İade: </span>
                              <span className="font-semibold text-emerald-700">
                                {String(item.return_date).slice(0, 10)}
                              </span>
                            </div>
                          )}
                        </td>
                        <td className="py-3.5 px-4">
                          {isReturned ? (
                            <div className="space-y-1">
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-300">
                                <Clock className="w-3 h-3 text-amber-700" />
                                İade Edildi (Ödenmedi)
                              </span>
                              <div className="text-[11px] text-slate-500 font-medium">
                                Toplam {item.overdue_days} gün gecikme
                              </div>
                            </div>
                          ) : (
                            <div className="space-y-1">
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-extrabold bg-rose-600 text-white shadow-2xs">
                                <AlertTriangle className="w-3 h-3" />
                                OVERDUE ({item.overdue_days} Gün Gecikti)
                              </span>
                              <div className="text-[11px] text-rose-600 font-semibold">
                                Kitap henüz teslim edilmedi
                              </div>
                            </div>
                          )}
                        </td>
                        <td className="py-3.5 px-4">
                          <div className="text-base font-extrabold text-rose-700">
                            {penalty.toFixed(2)} TL
                          </div>
                          <span className="inline-block px-2 py-0.5 rounded-md text-[10px] font-bold bg-rose-100 text-rose-800">
                            Tahsil Edilmedi
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <button
                            onClick={() => handleCollectPenalty(item)}
                            disabled={isCollecting}
                            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white text-xs font-bold shadow-2xs transition-colors cursor-pointer"
                            title="Elden ödeme alındığında borcu kapat"
                          >
                            <Check className={`w-4 h-4 ${isCollecting ? 'animate-spin' : ''}`} />
                            {isCollecting ? 'Tahsil Ediliyor...' : 'Tahsil Et / Borcu Kapat'}
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          )}

          {/* Sistem Logları Tablosu */}
          {subTab === 'logs' && (
            <table className="w-full text-left border-collapse min-w-[760px]">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3.5 px-4 w-44">Tarih / Saat</th>
                  <th className="py-3.5 px-4 w-32">Kategori</th>
                  <th className="py-3.5 px-4 w-28">Seviye</th>
                  <th className="py-3.5 px-4">Detaylı Açıklama</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {systemLogs.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-12 text-center text-slate-400 text-xs">
                      {logsLoading ? (
                        <div className="flex items-center justify-center gap-2 text-indigo-600 font-semibold">
                          <RefreshCw className="w-4 h-4 animate-spin" />
                          Sistem logları yükleniyor...
                        </div>
                      ) : (
                        'Seçilen filtrelere uygun sistem logu bulunamadı.'
                      )}
                    </td>
                  </tr>
                ) : (
                  systemLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3.5 px-4 text-xs font-mono text-slate-600 whitespace-nowrap">
                        {formatTimestamp(log.timestamp)}
                      </td>
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        {getCategoryBadge(log.category)}
                      </td>
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        {getLevelBadge(log.level)}
                      </td>
                      <td className="py-3.5 px-4 text-slate-800 font-medium break-words text-xs sm:text-sm">
                        {log.message}
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
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-xl max-h-[92vh] flex flex-col overflow-hidden my-auto">
            <div className="px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between shrink-0">
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
                  {/* ISBN İLE OTOMATİK DOLDURMA KUTUSU */}
                  <div className="p-4 rounded-2xl bg-gradient-to-r from-indigo-50/90 via-purple-50/60 to-slate-50 border border-indigo-200/80 space-y-2.5">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-indigo-950 flex items-center gap-1.5">
                        <Sparkles className="w-4 h-4 text-indigo-600" />
                        ISBN ile Otomatik Doldur (OpenLibrary / Google Books)
                      </span>
                      {lookupLoading && (
                        <span className="text-[11px] font-semibold text-indigo-600 flex items-center gap-1">
                          <RefreshCw className="w-3 h-3 animate-spin" />
                          Sorgulanıyor...
                        </span>
                      )}
                    </div>
                    <div className="flex flex-col sm:flex-row gap-2">
                      <div className="relative flex-1">
                        <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                        <input
                          type="text"
                          value={lookupIsbn}
                          onChange={(e) => setLookupIsbn(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.preventDefault();
                              handleLookupIsbn();
                            }
                          }}
                          placeholder="Örn: 9780140328721 veya 9780451524935"
                          className="w-full pl-9 pr-3 py-2 rounded-xl border border-indigo-200 bg-white text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => handleLookupIsbn()}
                        disabled={lookupLoading}
                        className="py-2 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors cursor-pointer shrink-0 shadow-xs shadow-indigo-200"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${lookupLoading ? 'animate-spin' : ''}`} />
                        Bilgileri Getir
                      </button>
                    </div>

                    {/* Hızlı Test Örnekleri */}
                    <div className="flex flex-wrap items-center gap-1.5 pt-0.5 text-[11px] text-slate-500">
                      <span className="font-semibold text-slate-600">Örnek ISBN'ler:</span>
                      <button
                        type="button"
                        onClick={() => {
                          setLookupIsbn('9780140328721');
                          handleLookupIsbn('9780140328721');
                        }}
                        className="px-2 py-0.5 rounded-md bg-white border border-indigo-200 text-indigo-700 hover:bg-indigo-50 font-mono font-medium transition-colors cursor-pointer"
                      >
                        9780140328721 (Fantastic Mr. Fox)
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setLookupIsbn('9780451524935');
                          handleLookupIsbn('9780451524935');
                        }}
                        className="px-2 py-0.5 rounded-md bg-white border border-indigo-200 text-indigo-700 hover:bg-indigo-50 font-mono font-medium transition-colors cursor-pointer"
                      >
                        9780451524935 (1984 - George Orwell)
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Kitap Başlığı *
                    </label>
                    <input
                      type="text"
                      required
                      value={bookForm.title}
                      onChange={(e) => setBookForm({ ...bookForm, title: e.target.value })}
                      placeholder="Örn: Tutunamayanlar"
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

                  {/* Kitap Kapağı Görsel URL (cover_url) */}
                  <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-2">
                    <label className="block text-xs font-bold text-slate-700 flex items-center gap-1.5">
                      <ImageIcon className="w-3.5 h-3.5 text-indigo-600" />
                      Kitap Kapağı Görsel Adresi (cover_url)
                    </label>
                    <div className="flex items-center gap-3">
                      <div className="flex-1">
                        <input
                          type="url"
                          value={bookForm.cover_url || ''}
                          onChange={(e) =>
                            setBookForm({ ...bookForm, cover_url: e.target.value })
                          }
                          placeholder="https://covers.openlibrary.org/b/id/...-L.jpg"
                          className="w-full px-3.5 py-2 rounded-xl border border-slate-200 bg-white text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </div>
                      {bookForm.cover_url && (
                        <div className="relative w-12 h-16 rounded-lg overflow-hidden border border-slate-200 bg-white shrink-0 shadow-2xs group">
                          <img
                            src={bookForm.cover_url}
                            alt="Önizleme"
                            className="w-full h-full object-cover"
                            onError={(e) => {
                              e.currentTarget.style.display = 'none';
                            }}
                          />
                          <button
                            type="button"
                            onClick={() => setBookForm({ ...bookForm, cover_url: '' })}
                            title="Kapağı Kaldır"
                            className="absolute inset-0 bg-slate-900/60 text-white opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 1. AKILLI YAYINEVİ SEÇİMİ (ARA VEYA YOKSA EKLE) */}
                  <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-2.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                        <Building2 className="w-3.5 h-3.5 text-indigo-600" />
                        Yayınevi (Mevcuttan Seç veya Yeni Yaz)
                      </label>
                      {selectedPublisherObj && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg text-xs font-bold bg-indigo-100 text-indigo-800 border border-indigo-200">
                          Seçili: {selectedPublisherObj.name}
                          <button
                            type="button"
                            onClick={() => setBookForm({ ...bookForm, publisher_id: '' })}
                            className="hover:text-rose-600 ml-1"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </span>
                      )}
                    </div>

                    <div className="relative flex gap-2">
                      <div className="relative flex-1">
                        <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                        <input
                          type="text"
                          value={publisherQuery}
                          onChange={(e) => setPublisherQuery(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && publisherQuery.trim()) {
                              e.preventDefault();
                              handleQuickCreatePublisher(publisherQuery);
                            }
                          }}
                          placeholder="Yayınevi ara veya listede yoksa yeni adını yazın..."
                          className="w-full pl-8 pr-3 py-1.5 rounded-xl border border-slate-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </div>

                      {publisherQuery.trim() && !exactPublisherExists && (
                        <button
                          type="button"
                          disabled={inlineCreating}
                          onClick={() => handleQuickCreatePublisher(publisherQuery)}
                          className="shrink-0 inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-2xs cursor-pointer"
                        >
                          <Plus className="w-3.5 h-3.5" />
                          "{publisherQuery.trim()}" Ekle & Seç
                        </button>
                      )}
                    </div>

                    <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto pt-1">
                      {filteredPublishers.map((p) => {
                        const isSelected = bookForm.publisher_id === p.id;
                        return (
                          <button
                            key={p.id}
                            type="button"
                            onClick={() =>
                              setBookForm({
                                ...bookForm,
                                publisher_id: isSelected ? '' : p.id,
                              })
                            }
                            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                              isSelected
                                ? 'bg-indigo-600 text-white shadow-2xs'
                                : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-100'
                            }`}
                          >
                            {isSelected && <Check className="w-3 h-3" />}
                            {p.name}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* 2. AKILLI YAZAR SEÇİMİ (ÇOKLU SEÇİM + ARA VEYA YOKSA EKLE) */}
                  <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-2.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                        <Users className="w-3.5 h-3.5 text-indigo-600" />
                        Yazarlar (Çoklu Seçim — Ara veya Yeni Yazar Ekle)
                      </label>
                      <span className="text-[11px] font-semibold text-slate-500">
                        {bookForm.author_ids.length} yazar seçili
                      </span>
                    </div>

                    {/* Seçili Yazarlar Rozetleri */}
                    {bookForm.author_ids.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pb-1">
                        {bookForm.author_ids.map((id) => {
                          const a = authors.find((item) => item.id === id);
                          if (!a) return null;
                          return (
                            <span
                              key={id}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-indigo-100 text-indigo-800 border border-indigo-200"
                            >
                              {a.first_name} {a.last_name}
                              <button
                                type="button"
                                onClick={() =>
                                  setBookForm({
                                    ...bookForm,
                                    author_ids: toggleSelection(bookForm.author_ids, id),
                                  })
                                }
                                className="hover:text-rose-600 ml-0.5"
                              >
                                <X className="w-3 h-3" />
                              </button>
                            </span>
                          );
                        })}
                      </div>
                    )}

                    <div className="relative flex gap-2">
                      <div className="relative flex-1">
                        <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                        <input
                          type="text"
                          value={authorQuery}
                          onChange={(e) => setAuthorQuery(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && authorQuery.trim()) {
                              e.preventDefault();
                              handleQuickCreateAuthor(authorQuery);
                            }
                          }}
                          placeholder="Yazar ara veya listede yoksa 'Ad Soyad' yazıp ekleyin..."
                          className="w-full pl-8 pr-3 py-1.5 rounded-xl border border-slate-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </div>

                      {authorQuery.trim() && !exactAuthorExists && (
                        <button
                          type="button"
                          disabled={inlineCreating}
                          onClick={() => handleQuickCreateAuthor(authorQuery)}
                          className="shrink-0 inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-2xs cursor-pointer"
                        >
                          <Plus className="w-3.5 h-3.5" />
                          "{authorQuery.trim()}" Ekle & Seç
                        </button>
                      )}
                    </div>

                    <div className="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto pt-1">
                      {filteredAuthors.map((a) => {
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
                  </div>

                  {/* 3. AKILLI KATEGORİ SEÇİMİ (ÇOKLU SEÇİM + ARA VEYA YOKSA EKLE) */}
                  <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-2.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                        <Tag className="w-3.5 h-3.5 text-indigo-600" />
                        Kategoriler (Çoklu Seçim — Ara veya Yeni Kategori Ekle)
                      </label>
                      <span className="text-[11px] font-semibold text-slate-500">
                        {bookForm.category_ids.length} kategori seçili
                      </span>
                    </div>

                    {/* Seçili Kategori Rozetleri */}
                    {bookForm.category_ids.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pb-1">
                        {bookForm.category_ids.map((id) => {
                          const c = categories.find((item) => item.id === id);
                          if (!c) return null;
                          return (
                            <span
                              key={id}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-indigo-100 text-indigo-800 border border-indigo-200"
                            >
                              {c.name}
                              <button
                                type="button"
                                onClick={() =>
                                  setBookForm({
                                    ...bookForm,
                                    category_ids: toggleSelection(bookForm.category_ids, id),
                                  })
                                }
                                className="hover:text-rose-600 ml-0.5"
                              >
                                <X className="w-3 h-3" />
                              </button>
                            </span>
                          );
                        })}
                      </div>
                    )}

                    <div className="relative flex gap-2">
                      <div className="relative flex-1">
                        <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                        <input
                          type="text"
                          value={categoryQuery}
                          onChange={(e) => setCategoryQuery(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && categoryQuery.trim()) {
                              e.preventDefault();
                              handleQuickCreateCategory(categoryQuery);
                            }
                          }}
                          placeholder="Kategori ara veya listede yoksa yeni adını yazın..."
                          className="w-full pl-8 pr-3 py-1.5 rounded-xl border border-slate-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </div>

                      {categoryQuery.trim() && !exactCategoryExists && (
                        <button
                          type="button"
                          disabled={inlineCreating}
                          onClick={() => handleQuickCreateCategory(categoryQuery)}
                          className="shrink-0 inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-2xs cursor-pointer"
                        >
                          <Plus className="w-3.5 h-3.5" />
                          "{categoryQuery.trim()}" Ekle & Seç
                        </button>
                      )}
                    </div>

                    <div className="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto pt-1">
                      {filteredCategories.map((c) => {
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
                  disabled={saving || inlineCreating}
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
