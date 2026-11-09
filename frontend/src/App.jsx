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
  AlertTriangle,
  ShieldAlert,
  ShieldCheck,
  Banknote,
  Clock,
  CreditCard,
  ArrowRight,
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
  const [myActiveBorrowings, setMyActiveBorrowings] = useState([]);
  const [authModalMode, setAuthModalMode] = useState(null); // null | 'login' | 'register'
  const [selectedBook, setSelectedBook] = useState(null);
  const [accountAlertOpen, setAccountAlertOpen] = useState(false);
  const [adminAlertOpen, setAdminAlertOpen] = useState(false);
  const [adminNavTarget, setAdminNavTarget] = useState({
    subTab: 'books',
    filter: 'ALL',
  });

  // Çoklu Kütüphane (Multi-Tenant) State'leri
  const [allPublicLibraries, setAllPublicLibraries] = useState([]);
  const [myMemberships, setMyMemberships] = useState([]);
  const [myLibraryRequests, setMyLibraryRequests] = useState([]);
  const [activeLibraryId, setActiveLibraryId] = useState(
    () => localStorage.getItem('active_library_id') || ''
  );

  // Kütüphaneye Katılma / Yeni Kütüphane Oluşturma Modalı State'leri
  const [libraryModalMode, setLibraryModalMode] = useState(null); // null | 'apply' | 'create'
  const [applyForm, setApplyForm] = useState({
    library_name: '',
    phone: '',
    identity_or_student_no: '',
    department_or_address: '',
    application_note: '',
  });
  const [applySubmitting, setApplySubmitting] = useState(false);
  const [applySuccessMessage, setApplySuccessMessage] = useState('');

  const [createLibForm, setCreateLibForm] = useState({
    name: '',
    description: '',
    daily_fine_amount: 5.0,
    max_borrow_days: 14,
    max_books_per_user: 3,
    penalty_rules_text:
      'Kitaplar zamanında teslim edilmelidir. Geciken her gün için kütüphanenin belirlediği günlük gecikme cezası uygulanır.',
  });
  const [createLibSubmitting, setCreateLibSubmitting] = useState(false);
  const [createLibSuccessBanner, setCreateLibSuccessBanner] = useState('');

  const isSystemAdmin = Boolean(
    user?.is_system_admin ||
      user?.roles?.includes('SYSTEM_ADMIN') ||
      user?.roles?.includes('ADMIN')
  );

  // Kullanıcının erişebileceği onaylı kütüphaneler listesi
  const approvedLibraries = React.useMemo(() => {
    if (!user) {
      return allPublicLibraries;
    }
    if (isSystemAdmin) {
      return allPublicLibraries.map((lib) => ({
        ...lib,
        membership_role: 'LIBRARY_ADMIN',
        membership_status: 'APPROVED',
      }));
    }
    return (myMemberships || [])
      .filter((m) => m.status === 'APPROVED')
      .map((m) => {
        const pub = allPublicLibraries.find((l) => String(l.id) === String(m.library_id));
        return {
          id: m.library_id,
          name: m.library_name || pub?.name || 'Kütüphane',
          description: pub?.description || '',
          daily_fine_amount: m.library_daily_fine_amount ?? pub?.daily_fine_amount ?? 5.0,
          max_borrow_days: m.library_max_borrow_days ?? pub?.max_borrow_days ?? 14,
          max_books_per_user: m.library_max_books_per_user ?? pub?.max_books_per_user ?? 3,
          penalty_rules_text: pub?.penalty_rules_text || '',
          membership_role: m.role,
          membership_status: m.status,
        };
      });
  }, [user, isSystemAdmin, allPublicLibraries, myMemberships]);

  const activeLibrary = React.useMemo(() => {
    if (approvedLibraries.length === 0) return null;
    return (
      approvedLibraries.find((l) => String(l.id) === String(activeLibraryId)) ||
      approvedLibraries[0]
    );
  }, [approvedLibraries, activeLibraryId]);

  useEffect(() => {
    if (activeLibrary && String(activeLibrary.id) !== String(activeLibraryId)) {
      setActiveLibraryId(String(activeLibrary.id));
      localStorage.setItem('active_library_id', String(activeLibrary.id));
    } else if (!activeLibrary && user && !isSystemAdmin && approvedLibraries.length === 0) {
      setActiveLibraryId('');
    }
  }, [activeLibrary, activeLibraryId, user, isSystemAdmin, approvedLibraries.length]);

  const handleSelectLibrary = (libId) => {
    setActiveLibraryId(String(libId));
    localStorage.setItem('active_library_id', String(libId));
    setPage(1);
  };

  const isActiveLibraryAdmin = Boolean(
    isSystemAdmin || activeLibrary?.membership_role === 'LIBRARY_ADMIN'
  );
  const canAccessAdmin = Boolean(
    isSystemAdmin ||
      isActiveLibraryAdmin ||
      (myMemberships || []).some(
        (m) => m.status === 'APPROVED' && m.role === 'LIBRARY_ADMIN'
      )
  );
  const userHasApprovedLibrary = Boolean(
    !user || isSystemAdmin || approvedLibraries.length > 0
  );

  // Bildirimler & Aksiyon Merkezi State
  const [notifications, setNotifications] = useState({
    total_count: 0,
    user_action_count: 0,
    admin_action_count: 0,
    pending_penalty_approvals: 0,
    pending_return_approvals: 0,
    pending_borrow_approvals: 0,
    items: [],
  });

  const fetchNotifications = useCallback(async (showAdminPopup = false) => {
    const token = getToken();
    if (!token) {
      setNotifications({
        total_count: 0,
        user_action_count: 0,
        admin_action_count: 0,
        pending_penalty_approvals: 0,
        pending_return_approvals: 0,
        pending_borrow_approvals: 0,
        items: [],
      });
      return;
    }
    try {
      const data = await api.getNotifications();
      const notifData = data || {
        total_count: 0,
        user_action_count: 0,
        admin_action_count: 0,
        pending_penalty_approvals: 0,
        pending_return_approvals: 0,
        pending_borrow_approvals: 0,
        items: [],
      };
      setNotifications(notifData);

      // Yönetici kullanıcıda onay bekleyen ödeme veya iade varsa açılır pencere (modal) uyarısını tetikle
      if (
        showAdminPopup &&
        (Number(notifData.pending_penalty_approvals || 0) > 0 ||
          Number(notifData.pending_return_approvals || 0) > 0 ||
          Number(notifData.pending_borrow_approvals || 0) > 0)
      ) {
        setAdminAlertOpen(true);
      }
    } catch {
      // ignore
    }
  }, []);

  const fetchLibrariesAndMemberships = useCallback(async () => {
    try {
      const pubLibs = await api.getLibraries().catch(() => []);
      setAllPublicLibraries(pubLibs || []);
      if (pubLibs?.length > 0 && !applyForm.library_name) {
        setApplyForm((prev) => ({
          ...prev,
          library_name: prev.library_name || pubLibs[0].name,
        }));
      }
      if (getToken()) {
        const [mems, reqs] = await Promise.all([
          api.getMyMemberships().catch(() => []),
          api.getMyLibraryRequests().catch(() => []),
        ]);
        setMyMemberships(mems || []);
        setMyLibraryRequests(reqs || []);
      } else {
        setMyMemberships([]);
        setMyLibraryRequests([]);
      }
    } catch {
      // ignore
    }
  }, [applyForm.library_name]);

  const fetchMyActiveBorrowings = useCallback(async (libId = activeLibrary?.id) => {
    const token = getToken();
    if (!token) {
      setMyActiveBorrowings([]);
      return;
    }
    try {
      const list = await api.getMyBorrowings(libId || '');
      const active = (list || []).filter(
        (b) => b.status !== 'RETURNED' && b.approval_status !== 'REJECTED'
      );
      setMyActiveBorrowings(active);
    } catch {
      setMyActiveBorrowings([]);
    }
  }, [activeLibrary?.id]);

  const checkAndTriggerAccountAlert = useCallback((me) => {
    if (!me) return;
    const hasBan = Boolean(me.is_banned);
    const hasOverdue = Number(me.overdue_books_count || 0) > 0;
    const hasUnpaidFee = Number(me.unpaid_penalty_total || 0) > 0;
    const hasPendingPayment = Number(me.pending_penalty_approval_count || 0) > 0;
    const hasAlertItems = Array.isArray(me.alert_items) && me.alert_items.length > 0;
    if (hasBan || hasOverdue || hasUnpaidFee || hasPendingPayment || hasAlertItems) {
      setAccountAlertOpen(true);
    }
  }, []);

  const refreshCurrentUser = useCallback(async (showPopup = false) => {
    await fetchLibrariesAndMemberships();
    const token = getToken();
    if (!token) return;
    try {
      const me = await api.getMe();
      setUser(me);
      if (Array.isArray(me?.memberships)) {
        setMyMemberships(me.memberships);
      }
      fetchMyActiveBorrowings();
      if (showPopup) {
        checkAndTriggerAccountAlert(me);
        const isAdminRole =
          me?.is_system_admin ||
          me?.roles?.includes('SYSTEM_ADMIN') ||
          me?.roles?.includes('ADMIN') ||
          me?.roles?.includes('LIBRARY_ADMIN');
        if (isAdminRole) {
          fetchNotifications(true);
        } else {
          fetchNotifications(false);
        }
      } else {
        fetchNotifications(false);
      }
    } catch {
      // ignore
    }
  }, [
    checkAndTriggerAccountAlert,
    fetchNotifications,
    fetchMyActiveBorrowings,
    fetchLibrariesAndMemberships,
  ]);

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

  // Check current user & notifications on mount
  useEffect(() => {
    refreshCurrentUser(true);
  }, [refreshCurrentUser]);

  // Load filter dropdown options (Authors, Categories, Publishers) with session caching
  const fetchFilterMetadata = useCallback(async (force = false) => {
    try {
      if (!force) {
        const cached = sessionStorage.getItem('kutuphane_metadata');
        if (cached) {
          const parsed = JSON.parse(cached);
          if (parsed?.authors && parsed?.categories && parsed?.publishers) {
            setAuthorsList(parsed.authors);
            setCategoriesList(parsed.categories);
            setPublishersList(parsed.publishers);
            return;
          }
        }
      }

      const [a, c, p] = await Promise.all([
        api.getAuthors(),
        api.getCategories(),
        api.getPublishers(),
      ]);
      const authors = a || [];
      const categories = c || [];
      const publishers = p || [];
      setAuthorsList(authors);
      setCategoriesList(categories);
      setPublishersList(publishers);
      sessionStorage.setItem(
        'kutuphane_metadata',
        JSON.stringify({ authors, categories, publishers })
      );
    } catch {
      // ignore initial metadata errors if backend is starting
    }
  }, []);

  useEffect(() => {
    fetchFilterMetadata();
  }, [fetchFilterMetadata]);

  // Load paginated & filtered books (scoped to activeLibrary)
  const fetchBooks = useCallback(async () => {
    if (user && !isSystemAdmin && approvedLibraries.length === 0) {
      setBooksData({ items: [], total: 0, page: 1, limit: 8, total_pages: 1 });
      setLoadingBooks(false);
      return;
    }
    setLoadingBooks(true);
    try {
      const targetLibId = activeLibrary?.id || activeLibraryId || undefined;
      const res = await api.getBooks({
        page,
        limit,
        search: search.trim() || undefined,
        category: categoryFilter || undefined,
        author: authorFilter || undefined,
        publisher: publisherFilter || undefined,
        library_id: targetLibId,
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
    user,
    isSystemAdmin,
    approvedLibraries.length,
    activeLibrary?.id,
    activeLibraryId,
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

  // Sekme tekrar Katalog'a geçtiğinde stok ve aktif ödünç kitapları anında tazele
  useEffect(() => {
    if (activeTab === 'catalog') {
      fetchBooks();
      if (getToken()) {
        fetchMyActiveBorrowings();
      }
    }
  }, [activeTab, fetchBooks, fetchMyActiveBorrowings]);

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

  const handleNotificationAction = (item) => {
    if (!item) return;

    if (item.target === 'ADMIN') {
      if (item.type === 'ADMIN_PENDING_PAYMENT') {
        setAdminNavTarget({ subTab: 'penalties', filter: 'PENDING_APPROVAL' });
        setActiveTab('admin');
      } else if (item.type === 'ADMIN_PENDING_RETURN') {
        setAdminNavTarget({ subTab: 'workflow', filter: 'RETURNS' });
        setActiveTab('admin');
      } else if (item.type === 'ADMIN_PENDING_BORROW') {
        setAdminNavTarget({ subTab: 'workflow', filter: 'BORROWS' });
        setActiveTab('admin');
      } else {
        setAdminNavTarget({ subTab: 'workflow', filter: 'ALL' });
        setActiveTab('admin');
      }
      return;
    }

    // Kullanıcı Aksiyonları
    if (item.type === 'RESERVATION_READY') {
      if (item.meta?.book_id) {
        const found = booksData.items.find((b) => b.id === item.meta.book_id);
        if (found) {
          setSelectedBook(found);
          return;
        }
      }
      setActiveTab('mylibrary');
      return;
    }

    setActiveTab('mylibrary');
  };

  const handleDismissNotification = useCallback(async (item) => {
    if (!item) return;
    const borrowingId = item.meta?.borrowing_id;

    // 1. İyimser güncelleme (State'ten hemen kaldır)
    setNotifications((prev) => {
      if (!prev) return prev;
      const nextItems = (prev.items || []).filter((i) => i.id !== item.id);
      const isUserItem = item.target === 'USER';
      const isAdminItem = item.target === 'ADMIN';
      return {
        ...prev,
        items: nextItems,
        total_count: Math.max(0, (prev.total_count || 1) - 1),
        user_action_count: isUserItem
          ? Math.max(0, (prev.user_action_count || 1) - 1)
          : prev.user_action_count,
        admin_action_count: isAdminItem
          ? Math.max(0, (prev.admin_action_count || 1) - 1)
          : prev.admin_action_count,
      };
    });

    // 2. Backend'e bildirimi okundu olarak kaydet
    if (borrowingId && item.type === 'BORROW_REJECTED') {
      try {
        await api.dismissRejectionNotification(borrowingId);
        fetchMyActiveBorrowings();
      } catch {
        // ignore
      }
    }
  }, [fetchMyActiveBorrowings]);

  const handleOpenActiveBookDetail = async (borrow) => {
    if (!borrow?.book_id) return;
    try {
      const book = await api.getBook(borrow.book_id);
      setSelectedBook(book);
    } catch {
      setActiveTab('mylibrary');
    }
  };

  const handleLogout = () => {
    setToken(null);
    setUser(null);
    setMyActiveBorrowings([]);
    setMyMemberships([]);
    setMyLibraryRequests([]);
    setActiveTab('catalog');
    notify('Oturumunuz güvenli bir şekilde kapatıldı.', 'info');
  };

  // Kütüphane İsmi ile Katılma Başvurusu Gönder
  const handleApplyToLibrarySubmit = async (e) => {
    e.preventDefault();
    if (!applyForm.library_name.trim()) {
      notify('Lütfen katılmak istediğiniz kütüphanenin adını girin veya seçin.', 'error');
      return;
    }
    if (
      !applyForm.phone.trim() ||
      !applyForm.identity_or_student_no.trim() ||
      !applyForm.department_or_address.trim()
    ) {
      notify('Lütfen Telefon, Öğrenci/Kurum/TC No ve Bölüm/Adres bilgilerini eksiksiz girin.', 'error');
      return;
    }
    setApplySubmitting(true);
    setApplySuccessMessage('');
    try {
      const res = await api.applyToLibrary({
        library_name: applyForm.library_name.trim(),
        phone: applyForm.phone.trim(),
        identity_or_student_no: applyForm.identity_or_student_no.trim(),
        department_or_address: applyForm.department_or_address.trim(),
        application_note: applyForm.application_note.trim() || undefined,
      });
      const msg = `"${res?.library_name || applyForm.library_name}" kütüphanesine katılma başvurunuz kütüphane yöneticisinin onayına (PENDING) gönderilmiştir.`;
      setApplySuccessMessage(msg);
      notify(msg, 'success');
      setApplyForm((prev) => ({
        ...prev,
        application_note: '',
      }));
      await refreshCurrentUser(false);
    } catch (err) {
      notify(err.message || 'Kütüphane katılım başvurusu gönderilemedi', 'error');
    } finally {
      setApplySubmitting(false);
    }
  };

  // Yeni Kütüphane Oluşturma Talebi Gönder
  const handleCreateLibraryRequestSubmit = async (e) => {
    e.preventDefault();
    if (!createLibForm.name.trim()) {
      notify('Lütfen oluşturulacak kütüphanenin adını girin.', 'error');
      return;
    }
    setCreateLibSubmitting(true);
    setCreateLibSuccessBanner('');
    try {
      await api.createLibraryRequest({
        name: createLibForm.name.trim(),
        description: createLibForm.description.trim() || null,
        daily_fine_amount: Number(createLibForm.daily_fine_amount || 5.0),
        max_borrow_days: Number(createLibForm.max_borrow_days || 14),
        max_books_per_user: Number(createLibForm.max_books_per_user || 3),
        penalty_rules_text: createLibForm.penalty_rules_text.trim() || null,
      });
      const exactNotice =
        'Kütüphane oluşturma talebiniz Sistem Yöneticisi onayına gönderilmiştir. Onaylandığında bu kütüphanenin yöneticisi olacaksınız.';
      setCreateLibSuccessBanner(exactNotice);
      notify(exactNotice, 'success');
      setCreateLibForm({
        name: '',
        description: '',
        daily_fine_amount: 5.0,
        max_borrow_days: 14,
        max_books_per_user: 3,
        penalty_rules_text:
          'Kitaplar zamanında teslim edilmelidir. Geciken her gün için kütüphanenin belirlediği günlük gecikme cezası uygulanır.',
      });
      await refreshCurrentUser(false);
    } catch (err) {
      notify(err.message || 'Kütüphane oluşturma talebi gönderilemedi', 'error');
    } finally {
      setCreateLibSubmitting(false);
    }
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
        notifications={notifications}
        onNotificationAction={handleNotificationAction}
        onDismissNotification={handleDismissNotification}
        approvedLibraries={approvedLibraries}
        activeLibraryId={activeLibrary?.id || activeLibraryId}
        activeLibrary={activeLibrary}
        onSelectLibrary={handleSelectLibrary}
        onOpenLibraryModal={(mode) => {
          setApplySuccessMessage('');
          setCreateLibSuccessBanner('');
          setLibraryModalMode(mode);
        }}
        canAccessAdmin={canAccessAdmin}
        isSystemAdmin={isSystemAdmin}
        isActiveLibraryAdmin={isActiveLibraryAdmin}
      />

      {/* Üst Hesap Kısıtlama (Ban) veya Gecikme / Hasar-Kayıp Borç Bilgi Çubuğu */}
      {user &&
        (user.is_banned ||
          Number(user.overdue_books_count || 0) > 0 ||
          Number(user.unpaid_penalty_total || 0) > 0 ||
          Number(user.pending_penalty_approval_count || 0) > 0) && (
          <div className="bg-gradient-to-r from-rose-700 via-red-700 to-rose-800 text-white border-b border-rose-500">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
              <div className="flex items-center gap-2 font-semibold">
                <ShieldAlert className="w-4 h-4 text-amber-300 shrink-0" />
                <span>
                  {user.is_banned
                    ? `Hesabınız Yönetici Tarafından Kısıtlanmıştır (Banlı): ${
                        user.ban_reason ||
                        'Kitap iadeniz ve borç ödemeniz yapılana kadar yeni ödünç, rezervasyon ve yorum işlemleriniz kapalıdır.'
                      }`
                    : (user.pending_penalty_approval_count || 0) > 0
                    ? 'Ödemiş olduğunuz gecikme veya kayıp/hasar tazminat bedelinin yönetici tarafından onaylanması beklenmektedir. Yönetici ödemeyi aldığını onaylayana kadar yeni kitap ödünç alamaz veya rezervasyon oluşturamazsınız.'
                    : `Hesabınızda ${
                        user.overdue_books_count > 0
                          ? `${user.overdue_books_count} adet gecikmiş kitap`
                          : ''
                      }${
                        user.overdue_books_count > 0 && user.unpaid_penalty_total > 0
                          ? ' ve '
                          : ''
                      }${
                        user.unpaid_penalty_total > 0
                          ? `${Number(user.unpaid_penalty_total).toFixed(2)} TL ödenmemiş gecikme/hasar/kayıp ücreti`
                          : ''
                      } bulunmaktadır.`}
                </span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => setAccountAlertOpen(true)}
                  className="px-3 py-1 rounded-lg bg-white/15 hover:bg-white/25 text-white font-bold transition-colors cursor-pointer"
                >
                  Detayları Gör
                </button>
                <button
                  onClick={() => setActiveTab('mylibrary')}
                  className="px-3 py-1 rounded-lg bg-amber-400 hover:bg-amber-300 text-slate-950 font-extrabold transition-colors cursor-pointer"
                >
                  Kitaplarım & Borç Öde
                </button>
              </div>
            </div>
          </div>
        )}

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        {activeTab === 'catalog' && (
          <div className="space-y-6">
            {user && !userHasApprovedLibrary ? (
              /* Yeni Kayıt Olan ve Henüz Hiçbir Kütüphanede Onaylı (APPROVED) Üyeliği Bulunmayan Kullanıcı Karşılama Ekranı */
              <div className="space-y-6">
                <div className="rounded-3xl bg-gradient-to-r from-indigo-900 via-indigo-800 to-violet-900 text-white p-6 sm:p-10 shadow-xl border border-indigo-700">
                  <div className="max-w-3xl space-y-3">
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-extrabold uppercase tracking-wider bg-amber-400 text-slate-950">
                      <Building2 className="w-3.5 h-3.5" />
                      ÇOKLU KÜTÜPHANE MİMARİSİ — HOŞ GELDİNİZ
                    </span>
                    <h1 className="text-2xl sm:text-3xl font-extrabold leading-tight">
                      Katalogları görüntülemek ve kitap ödünç alabilmek için bir kütüphaneye katılmanız gerekmektedir.
                    </h1>
                    <p className="text-xs sm:text-sm text-indigo-100 leading-relaxed">
                      Merhaba <strong>{user.first_name} {user.last_name}</strong>, sistemimizde her kütüphane bağımsız katalog ve ödünç kurallarıyla çalışmaktadır. Aşağıdan kütüphane ismi ile arama yaparak mevcut bir kütüphaneye katılma başvurusu yapabilir veya kendi kütüphanenizi oluşturmak için Sistem Yöneticisi onayına talep gönderebilirsiniz.
                    </p>
                  </div>
                </div>

                {/* Kullanıcının Bekleyen Başvuruları ve Kütüphane Kurulum Talepleri Özeti */}
                {(myMemberships.length > 0 || myLibraryRequests.length > 0) && (
                  <div className="bg-white rounded-3xl p-5 sm:p-6 border border-indigo-200 shadow-xs space-y-4">
                    <div className="flex items-center justify-between gap-2">
                      <h2 className="text-base font-extrabold text-slate-900 flex items-center gap-2">
                        <Clock className="w-5 h-5 text-indigo-600" />
                        Mevcut Kütüphane Başvurularınız & Kurulum Talepleriniz
                      </h2>
                      <button
                        type="button"
                        onClick={() => refreshCurrentUser(false)}
                        className="px-3 py-1.5 rounded-xl bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-bold cursor-pointer"
                      >
                        Durumu Kontrol Et / Yenile
                      </button>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {myMemberships.map((m) => (
                        <div
                          key={m.id}
                          className="p-4 rounded-2xl bg-slate-50 border border-slate-200 flex items-center justify-between gap-3 text-xs"
                        >
                          <div>
                            <span className="font-extrabold text-slate-900 text-sm block">
                              {m.library_name || 'Kütüphane'}
                            </span>
                            <span className="text-slate-500">
                              Katılım Başvurusu • Öğrenci/TC: {m.identity_or_student_no || '-'}
                            </span>
                            {m.ban_reason && (
                              <p className="text-rose-700 font-semibold mt-1">
                                Ban Notu: "{m.ban_reason}"
                              </p>
                            )}
                          </div>
                          <span
                            className={`px-2.5 py-1 rounded-full font-extrabold shrink-0 ${
                              m.status === 'PENDING'
                                ? 'bg-amber-100 text-amber-900 border border-amber-300'
                                : m.status === 'BANNED'
                                ? 'bg-rose-600 text-white'
                                : 'bg-slate-200 text-slate-700'
                            }`}
                          >
                            {m.status === 'PENDING'
                              ? 'Yönetici Onayı Bekliyor'
                              : m.status === 'BANNED'
                              ? 'Banlı (Kısıtlı)'
                              : 'Reddedildi'}
                          </span>
                        </div>
                      ))}

                      {myLibraryRequests.map((req) => (
                        <div
                          key={req.id}
                          className="p-4 rounded-2xl bg-violet-50/70 border border-violet-200 flex items-center justify-between gap-3 text-xs"
                        >
                          <div>
                            <span className="font-extrabold text-violet-950 text-sm block">
                              {req.name} (Yeni Kütüphane Kurulum Talebi)
                            </span>
                            <span className="text-violet-700">
                              Günlük Ceza: {req.daily_fine_amount} TL • Ödünç: {req.max_borrow_days} Gün
                            </span>
                          </div>
                          <span
                            className={`px-2.5 py-1 rounded-full font-extrabold shrink-0 ${
                              req.status === 'PENDING'
                                ? 'bg-amber-100 text-amber-900 border border-amber-300'
                                : req.status === 'APPROVED'
                                ? 'bg-emerald-100 text-emerald-800'
                                : 'bg-rose-100 text-rose-800'
                            }`}
                          >
                            {req.status === 'PENDING'
                              ? 'Sistem Yöneticisi Onayında'
                              : req.status === 'APPROVED'
                              ? 'Onaylandı'
                              : 'Reddedildi'}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* İki Sütunlu Başvuru ve Yeni Kütüphane Oluşturma Kartları */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* 1. Kütüphane İsmi ile Arama ve Katılma Başvurusu Formu */}
                  <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm space-y-4">
                    <div>
                      <span className="inline-block px-2.5 py-0.5 rounded-md text-[10px] font-extrabold uppercase bg-indigo-100 text-indigo-800 mb-1">
                        ADIM 1 • MEVCUT KÜTÜPHANEYE KATILIM
                      </span>
                      <h2 className="text-lg font-extrabold text-slate-900">
                        Kütüphane İsmiyle Katılma Başvurusu Yapın
                      </h2>
                      <p className="text-xs text-slate-500 mt-0.5">
                        Katılmak istediğiniz kütüphanenin adını arayın veya listeden seçin; başvuru bilgileriniz ilgili kütüphane yöneticisinin onayına düşecektir.
                      </p>
                    </div>

                    {applySuccessMessage && (
                      <div className="p-3.5 rounded-2xl bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs font-bold flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                        <span>{applySuccessMessage}</span>
                      </div>
                    )}

                    <form onSubmit={handleApplyToLibrarySubmit} className="space-y-3.5">
                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1">
                          Kütüphane İsmi (Arama / Seçim) *
                        </label>
                        <input
                          type="text"
                          required
                          value={applyForm.library_name}
                          onChange={(e) =>
                            setApplyForm((prev) => ({ ...prev, library_name: e.target.value }))
                          }
                          placeholder="Örn: Test Kütüphanesi"
                          className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                        {allPublicLibraries.length > 0 && (
                          <div className="flex flex-wrap items-center gap-1.5 mt-2">
                            <span className="text-[11px] text-slate-400 font-semibold">
                              Aktif Kütüphaneler:
                            </span>
                            {allPublicLibraries.map((lib) => (
                              <button
                                key={lib.id}
                                type="button"
                                onClick={() =>
                                  setApplyForm((prev) => ({ ...prev, library_name: lib.name }))
                                }
                                className={`px-2.5 py-1 rounded-lg text-xs font-bold border transition-all cursor-pointer ${
                                  applyForm.library_name.trim().toLowerCase() ===
                                  lib.name.toLowerCase()
                                    ? 'bg-indigo-600 text-white border-indigo-600'
                                    : 'bg-indigo-50 text-indigo-700 border-indigo-200 hover:bg-indigo-100'
                                }`}
                              >
                                {lib.name} ({lib.max_borrow_days} gün / {lib.daily_fine_amount} TL)
                              </button>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                          <label className="block text-xs font-bold text-slate-700 mb-1">
                            Telefon Numarası *
                          </label>
                          <input
                            type="text"
                            required
                            value={applyForm.phone}
                            onChange={(e) =>
                              setApplyForm((prev) => ({ ...prev, phone: e.target.value }))
                            }
                            placeholder="Örn: 0555 123 45 67"
                            className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-bold text-slate-700 mb-1">
                            Öğrenci / Kurum / TC No *
                          </label>
                          <input
                            type="text"
                            required
                            value={applyForm.identity_or_student_no}
                            onChange={(e) =>
                              setApplyForm((prev) => ({
                                ...prev,
                                identity_or_student_no: e.target.value,
                              }))
                            }
                            placeholder="Örn: 20261045 veya TC No"
                            className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          />
                        </div>
                      </div>

                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1">
                          Bölüm / Fakülte veya Adres Bilgisi *
                        </label>
                        <input
                          type="text"
                          required
                          value={applyForm.department_or_address}
                          onChange={(e) =>
                            setApplyForm((prev) => ({
                              ...prev,
                              department_or_address: e.target.value,
                            }))
                          }
                          placeholder="Örn: Bilgisayar Mühendisliği Bölümü / Merkez Kampüs"
                          className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1">
                          Katılım Notu (İsteğe Bağlı)
                        </label>
                        <input
                          type="text"
                          value={applyForm.application_note}
                          onChange={(e) =>
                            setApplyForm((prev) => ({
                              ...prev,
                              application_note: e.target.value,
                            }))
                          }
                          placeholder="Kütüphane yöneticisine iletmek istediğiniz not..."
                          className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </div>

                      <button
                        type="submit"
                        disabled={applySubmitting}
                        className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white font-extrabold text-xs sm:text-sm shadow-sm cursor-pointer transition-colors"
                      >
                        {applySubmitting
                          ? 'Başvuru Gönderiliyor...'
                          : 'Kütüphaneye Katılma Başvurusu Gönder'}
                      </button>
                    </form>
                  </div>

                  {/* 2. Yeni Kütüphane Oluşturma Talebi Formu */}
                  <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm space-y-4">
                    <div>
                      <span className="inline-block px-2.5 py-0.5 rounded-md text-[10px] font-extrabold uppercase bg-violet-100 text-violet-800 mb-1">
                        ALTERNATİF • YENİ KÜTÜPHANE KURULUMU
                      </span>
                      <h2 className="text-lg font-extrabold text-slate-900">
                        Yeni Bir Kütüphane Oluşturma Talebinde Bulunun
                      </h2>
                      <p className="text-xs text-slate-500 mt-0.5">
                        Kendi kurumunuz veya topluluğunuz için özel ödünç ve ceza kurallarına sahip yeni bir kütüphane oluşturabilirsiniz.
                      </p>
                    </div>

                    {createLibSuccessBanner && (
                      <div className="p-4 rounded-2xl bg-amber-50 border-2 border-amber-400 text-amber-950 text-xs sm:text-sm font-extrabold flex items-start gap-2.5">
                        <CheckCircle2 className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
                        <span>{createLibSuccessBanner}</span>
                      </div>
                    )}

                    <form onSubmit={handleCreateLibraryRequestSubmit} className="space-y-3.5">
                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1">
                          Yeni Kütüphane Adı (Benzersiz) *
                        </label>
                        <input
                          type="text"
                          required
                          value={createLibForm.name}
                          onChange={(e) =>
                            setCreateLibForm((prev) => ({ ...prev, name: e.target.value }))
                          }
                          placeholder="Örn: Mühendislik Fakültesi Kütüphanesi"
                          className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-violet-500"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1">
                          Kütüphane Açıklaması
                        </label>
                        <input
                          type="text"
                          value={createLibForm.description}
                          onChange={(e) =>
                            setCreateLibForm((prev) => ({
                              ...prev,
                              description: e.target.value,
                            }))
                          }
                          placeholder="Kütüphane hakkında kısa bilgi..."
                          className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
                        />
                      </div>

                      <div className="grid grid-cols-3 gap-2.5">
                        <div>
                          <label className="block text-[11px] font-bold text-slate-700 mb-1">
                            Günlük Ceza (TL)
                          </label>
                          <input
                            type="number"
                            step="0.5"
                            min="0"
                            required
                            value={createLibForm.daily_fine_amount}
                            onChange={(e) =>
                              setCreateLibForm((prev) => ({
                                ...prev,
                                daily_fine_amount: e.target.value,
                              }))
                            }
                            className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs sm:text-sm font-bold"
                          />
                        </div>
                        <div>
                          <label className="block text-[11px] font-bold text-slate-700 mb-1">
                            Ödünç Süresi (Gün)
                          </label>
                          <input
                            type="number"
                            min="1"
                            max="365"
                            required
                            value={createLibForm.max_borrow_days}
                            onChange={(e) =>
                              setCreateLibForm((prev) => ({
                                ...prev,
                                max_borrow_days: e.target.value,
                              }))
                            }
                            className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs sm:text-sm font-bold"
                          />
                        </div>
                        <div>
                          <label className="block text-[11px] font-bold text-slate-700 mb-1">
                            Kitap Limiti
                          </label>
                          <input
                            type="number"
                            min="1"
                            max="50"
                            required
                            value={createLibForm.max_books_per_user}
                            onChange={(e) =>
                              setCreateLibForm((prev) => ({
                                ...prev,
                                max_books_per_user: e.target.value,
                              }))
                            }
                            className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs sm:text-sm font-bold"
                          />
                        </div>
                      </div>

                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1">
                          Başlangıç Ceza ve Ödünç Kuralları Metni
                        </label>
                        <textarea
                          rows={2}
                          value={createLibForm.penalty_rules_text}
                          onChange={(e) =>
                            setCreateLibForm((prev) => ({
                              ...prev,
                              penalty_rules_text: e.target.value,
                            }))
                          }
                          className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs focus:outline-none focus:ring-2 focus:ring-violet-500"
                        />
                      </div>

                      <button
                        type="submit"
                        disabled={createLibSubmitting}
                        className="w-full py-2.5 px-4 rounded-xl bg-violet-700 hover:bg-violet-800 disabled:opacity-60 text-white font-extrabold text-xs sm:text-sm shadow-sm cursor-pointer transition-colors"
                      >
                        {createLibSubmitting
                          ? 'Talep Gönderiliyor...'
                          : 'Yeni Kütüphane Oluşturma Talebi Gönder'}
                      </button>
                    </form>
                  </div>
                </div>
              </div>
            ) : (
              <>
                {/* Hero Banner */}
                <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-indigo-900 via-indigo-800 to-violet-900 text-white p-6 sm:p-8 shadow-lg">
                  <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    <div className="max-w-2xl space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-white/15 backdrop-blur-xs text-indigo-100">
                          <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                          Dijital Katalog & Akıllı Rezervasyon Sistemi
                        </span>
                        {activeLibrary && (
                          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-extrabold bg-amber-400 text-slate-950">
                            <Building2 className="w-3.5 h-3.5" />
                            Aktif Kütüphane: {activeLibrary.name}
                          </span>
                        )}
                      </div>
                      <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
                        {activeLibrary
                          ? `${activeLibrary.name} Kataloğunu Keşfedin`
                          : 'Kütüphane Kataloğunu Keşfedin'}
                      </h1>
                      <p className="text-xs sm:text-sm text-indigo-100/90 leading-relaxed">
                        {activeLibrary
                          ? `Bu kütüphanede ödünç teslim süresi ${
                              activeLibrary.max_borrow_days || 14
                            } gün, gecikme durumunda günlük ceza ${Number(
                              activeLibrary.daily_fine_amount ?? 5
                            ).toFixed(2)} TL ve kişi başı aktif kitap limiti ${
                              activeLibrary.max_books_per_user || 3
                            } adettir.`
                          : 'Kitapları başlık, yazar, kategori veya yayınevine göre filtreleyin; stokta olan eserleri anında ödünç alın veya tükenen kitaplar için rezervasyon sırasına girin.'}
                      </p>
                    </div>

                    {user && (
                      <div className="flex flex-wrap items-center gap-2 shrink-0">
                        <button
                          type="button"
                          onClick={() => {
                            setApplySuccessMessage('');
                            setLibraryModalMode('apply');
                          }}
                          className="px-3.5 py-2 rounded-xl bg-white/15 hover:bg-white/25 text-white text-xs font-bold border border-white/20 cursor-pointer transition-colors"
                        >
                          + Başka Kütüphaneye Katıl
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setCreateLibSuccessBanner('');
                            setLibraryModalMode('create');
                          }}
                          className="px-3.5 py-2 rounded-xl bg-amber-400 hover:bg-amber-300 text-slate-950 text-xs font-extrabold cursor-pointer transition-colors"
                        >
                          + Yeni Kütüphane Oluştur
                        </button>
                      </div>
                    )}
                  </div>
                </div>

            {/* Kullanıcı Aktif Kitaplarım Bölümü (Ana Sayfa) */}
            {user && myActiveBorrowings.length > 0 && (
              <div className="bg-white rounded-3xl p-5 sm:p-6 border-2 border-indigo-100 shadow-xs space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-2xl bg-indigo-600 text-white flex items-center justify-center shadow-xs">
                      <BookOpen className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-base sm:text-lg font-black text-slate-900 tracking-tight">
                          Aktif Kitaplarım
                        </h2>
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-black bg-indigo-100 text-indigo-700">
                          {myActiveBorrowings.length} Kitap
                        </span>
                      </div>
                      <p className="text-xs text-slate-500">
                        Şu an üzerinizde bulunan veya onay sürecindeki ödünçleriniz
                      </p>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => setActiveTab('mylibrary')}
                    className="inline-flex items-center gap-1.5 text-xs font-bold text-indigo-600 hover:text-indigo-800 px-3.5 py-2 rounded-xl bg-indigo-50 hover:bg-indigo-100/80 transition-colors cursor-pointer self-start sm:self-auto"
                  >
                    <span>Tüm Kitaplarım & Rezervasyonlarım</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
                  {myActiveBorrowings.map((borrow) => {
                    const isPendingBorrow = borrow.approval_status === 'PENDING_BORROW';
                    const isPendingReturn = borrow.approval_status === 'PENDING_RETURN';
                    const isOverdue =
                      borrow.status === 'OVERDUE' ||
                      (borrow.overdue_days && borrow.overdue_days > 0);

                    return (
                      <div
                        key={borrow.id}
                        className="p-4 rounded-2xl bg-slate-50/80 hover:bg-indigo-50/40 border border-slate-200/90 hover:border-indigo-300 transition-all flex flex-col justify-between gap-3 group"
                      >
                        <div className="flex items-start gap-3">
                          {/* Kitap Kapak Küçük Resmi */}
                          <div className="w-12 h-16 rounded-xl bg-indigo-100 flex items-center justify-center shrink-0 overflow-hidden border border-slate-200">
                            {borrow.book_cover_url ? (
                              <img
                                src={borrow.book_cover_url}
                                alt={borrow.book_title || 'Kitap'}
                                className="w-full h-full object-cover"
                              />
                            ) : (
                              <BookOpen className="w-6 h-6 text-indigo-500" />
                            )}
                          </div>

                          <div className="min-w-0 flex-1">
                            <div className="mb-1">
                              {isPendingBorrow ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-300">
                                  <Clock className="w-3 h-3 text-amber-600 animate-pulse" />
                                  Ödünç Onayı Bekliyor
                                </span>
                              ) : isPendingReturn ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-indigo-100 text-indigo-900 border border-indigo-300">
                                  <ShieldCheck className="w-3 h-3 text-indigo-600 animate-pulse" />
                                  İade Kontrolünde
                                </span>
                              ) : isOverdue ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-extrabold bg-rose-600 text-white">
                                  <AlertCircle className="w-3 h-3" />
                                  Gecikmiş ({borrow.overdue_days || 1} Gün)
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                                  Ödünçte (Teslim Alındı)
                                </span>
                              )}
                            </div>

                            <h3
                              onClick={() => handleOpenActiveBookDetail(borrow)}
                              className="font-extrabold text-xs sm:text-sm text-slate-900 truncate hover:text-indigo-600 cursor-pointer"
                              title={borrow.book_title}
                            >
                              {borrow.book_title}
                            </h3>
                            {borrow.book_author && (
                              <p className="text-[11px] text-slate-500 truncate">
                                {borrow.book_author}
                              </p>
                            )}
                          </div>
                        </div>

                        <div className="pt-2 border-t border-slate-200/80 flex items-center justify-between text-xs">
                          <span className="text-slate-500 text-[11px]">
                            Son Teslim: <strong className={isOverdue ? 'text-rose-600' : 'text-slate-800'}>{borrow.due_date}</strong>
                          </span>
                          <button
                            type="button"
                            onClick={() => setActiveTab('mylibrary')}
                            className="text-[11px] font-bold text-indigo-600 hover:text-indigo-800 hover:underline cursor-pointer"
                          >
                            İade & Yönet →
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

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
                  const reservedCount = book.reserved_count || 0;
                  const queueIds = book.reservation_queue_user_ids || [];
                  const userQueueIdx = user ? queueIds.indexOf(user.id) : -1;
                  const userHasActiveSlot =
                    inStock && userQueueIdx >= 0 && userQueueIdx < book.stock_count;
                  const allStockReservedByOthers =
                    inStock && reservedCount >= book.stock_count && !userHasActiveSlot;

                  return (
                    <div
                      key={book.id}
                      onClick={() => setSelectedBook(book)}
                      className="group bg-white rounded-2xl border border-slate-200/90 hover:border-indigo-300 shadow-2xs hover:shadow-xl hover:shadow-indigo-100/50 transition-all duration-200 flex flex-col justify-between overflow-hidden cursor-pointer"
                    >
                      <div>
                        {/* Book Cover Image / Styled Showcase Banner (Kitap Kapağı Tam Sığdırma) */}
                        <div className="relative w-full h-64 bg-gradient-to-b from-slate-100/90 via-slate-50 to-slate-100/80 border-b border-slate-100 p-3.5 flex items-center justify-center overflow-hidden">
                          {/* Arka Planda Yumuşak Bulanık Atmosfer Katmanı */}
                          {book.cover_url && (
                            <img
                              src={book.cover_url}
                              alt=""
                              aria-hidden="true"
                              className="absolute inset-0 w-full h-full object-cover blur-2xl opacity-20 scale-125 pointer-events-none"
                            />
                          )}

                          {book.cover_url ? (
                            <img
                              src={book.cover_url}
                              alt={book.title}
                              className="relative z-0 max-h-56 max-w-[85%] object-contain rounded-lg shadow-md group-hover:shadow-xl group-hover:scale-105 transition-all duration-300"
                              onError={(e) => {
                                e.currentTarget.style.display = 'none';
                                if (e.currentTarget.nextElementSibling) {
                                  e.currentTarget.nextElementSibling.classList.remove('hidden');
                                  e.currentTarget.nextElementSibling.classList.add('flex');
                                }
                              }}
                            />
                          ) : null}
                          <div
                            className={`${
                              book.cover_url ? 'hidden' : 'flex'
                            } flex-col items-center justify-center w-full h-full bg-gradient-to-br from-indigo-500/10 via-purple-500/5 to-slate-100 text-indigo-400 group-hover:text-indigo-600 transition-colors`}
                          >
                            <BookOpen className="w-12 h-12 stroke-[1.5] opacity-60 group-hover:scale-110 transition-transform duration-300" />
                            <span className="text-[11px] font-medium text-slate-400 mt-1 font-mono">
                              {book.isbn}
                            </span>
                          </div>

                          {/* Status Badge Overlays */}
                          <div className="absolute top-3 left-3 flex flex-wrap gap-1.5 z-10">
                            <span
                              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold shadow-xs backdrop-blur-md ${
                                inStock
                                  ? 'bg-emerald-600/90 text-white'
                                  : 'bg-rose-600/90 text-white'
                              }`}
                            >
                              <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                              {inStock ? `Stok: ${book.stock_count}` : 'Tükendi (0)'}
                            </span>

                            {userHasActiveSlot ? (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-600 text-white shadow-xs">
                                Size Rezerveli
                              </span>
                            ) : allStockReservedByOthers ? (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500 text-white shadow-xs">
                                Başkasına Rezerveli ({reservedCount})
                              </span>
                            ) : reservedCount > 0 ? (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500 text-white shadow-xs">
                                Sırada: {reservedCount}
                              </span>
                            ) : null}
                          </div>

                          {book.published_year && (
                            <span className="absolute top-3 right-3 inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[11px] font-semibold text-slate-700 bg-white/90 backdrop-blur-md shadow-xs z-10">
                              <Calendar className="w-3 h-3 text-indigo-600" />
                              {book.published_year}
                            </span>
                          )}
                        </div>

                        {/* Book Title & Info */}
                        <div className="p-5 pt-4 space-y-2.5">
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
                            userHasActiveSlot
                              ? 'bg-emerald-100 text-emerald-800 group-hover:bg-emerald-600 group-hover:text-white'
                              : allStockReservedByOthers || !inStock
                              ? 'bg-amber-50 text-amber-800 group-hover:bg-amber-600 group-hover:text-white'
                              : 'bg-indigo-50 text-indigo-700 group-hover:bg-indigo-600 group-hover:text-white'
                          }`}
                        >
                          {userHasActiveSlot
                            ? 'Ödünç Al (Sıra Sizde)'
                            : allStockReservedByOthers
                            ? 'Rezerveli • Sıraya Gir'
                            : inStock
                            ? 'İncele & Ödünç Al'
                            : 'İncele & Rezerve Et'}
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
              </>
            )}
          </div>
        )}

        {activeTab === 'mylibrary' && user && (
          <MyLibraryView
            notify={notify}
            activeLibraryId={activeLibrary?.id || activeLibraryId}
            activeLibrary={activeLibrary}
            onSelectBook={(b) => setSelectedBook(b)}
            onCatalogChanged={() => {
              fetchBooks();
              refreshCurrentUser(false);
              fetchNotifications(false);
              fetchMyActiveBorrowings();
            }}
          />
        )}

        {activeTab === 'admin' && canAccessAdmin && (
          <AdminPanel
            notify={notify}
            initialSubTab={adminNavTarget.subTab}
            initialFilter={adminNavTarget.filter}
            activeLibraryId={activeLibrary?.id || activeLibraryId}
            activeLibrary={activeLibrary}
            isSystemAdmin={isSystemAdmin}
            user={user}
            onLibrariesChanged={() => {
              refreshCurrentUser(false);
            }}
            onSelectBook={(b) => setSelectedBook(b)}
            onCatalogChanged={() => {
              sessionStorage.removeItem('kutuphane_metadata');
              fetchFilterMetadata(true);
              fetchBooks();
              refreshCurrentUser(false);
              fetchNotifications(false);
              fetchMyActiveBorrowings();
            }}
          />
        )}
      </main>

      {/* Kütüphaneye Katılma Başvurusu / Yeni Kütüphane Oluşturma Modalı */}
      {libraryModalMode && user && (
        <div className="fixed inset-0 z-[9985] flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-xs overflow-y-auto">
          <div className="bg-white rounded-3xl shadow-2xl border border-slate-200 w-full max-w-lg overflow-hidden my-auto animate-in fade-in zoom-in-95 duration-150">
            <div className="px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setLibraryModalMode('apply')}
                  className={`px-3 py-1.5 rounded-xl text-xs font-extrabold cursor-pointer transition-colors ${
                    libraryModalMode === 'apply'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-200/70 text-slate-700 hover:bg-slate-200'
                  }`}
                >
                  Kütüphaneye Katıl
                </button>
                <button
                  type="button"
                  onClick={() => setLibraryModalMode('create')}
                  className={`px-3 py-1.5 rounded-xl text-xs font-extrabold cursor-pointer transition-colors ${
                    libraryModalMode === 'create'
                      ? 'bg-violet-700 text-white'
                      : 'bg-slate-200/70 text-slate-700 hover:bg-slate-200'
                  }`}
                >
                  Yeni Kütüphane Oluştur
                </button>
              </div>
              <button
                type="button"
                onClick={() => setLibraryModalMode(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {libraryModalMode === 'apply' ? (
              <form onSubmit={handleApplyToLibrarySubmit} className="p-6 space-y-4">
                <div>
                  <h3 className="text-base font-extrabold text-slate-900">
                    Kütüphane İsmiyle Katılma Başvurusu
                  </h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Katılmak istediğiniz kütüphanenin adını girin veya aşağıdan seçin. Başvurunuz kütüphane yöneticisinin onayına (PENDING) iletilecektir.
                  </p>
                </div>

                {applySuccessMessage && (
                  <div className="p-3.5 rounded-2xl bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs font-bold flex items-start gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    <span>{applySuccessMessage}</span>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">
                    Kütüphane İsmi *
                  </label>
                  <input
                    type="text"
                    required
                    value={applyForm.library_name}
                    onChange={(e) =>
                      setApplyForm((prev) => ({ ...prev, library_name: e.target.value }))
                    }
                    placeholder="Örn: Test Kütüphanesi"
                    className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  {allPublicLibraries.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 mt-2">
                      {allPublicLibraries.map((lib) => (
                        <button
                          key={lib.id}
                          type="button"
                          onClick={() =>
                            setApplyForm((prev) => ({ ...prev, library_name: lib.name }))
                          }
                          className={`px-2.5 py-1 rounded-lg text-xs font-bold border cursor-pointer ${
                            applyForm.library_name.trim().toLowerCase() ===
                            lib.name.toLowerCase()
                              ? 'bg-indigo-600 text-white border-indigo-600'
                              : 'bg-indigo-50 text-indigo-700 border-indigo-200'
                          }`}
                        >
                          {lib.name}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">
                      Telefon No *
                    </label>
                    <input
                      type="text"
                      required
                      value={applyForm.phone}
                      onChange={(e) =>
                        setApplyForm((prev) => ({ ...prev, phone: e.target.value }))
                      }
                      placeholder="0555 123 45 67"
                      className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs sm:text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">
                      Öğrenci / Kurum / TC No *
                    </label>
                    <input
                      type="text"
                      required
                      value={applyForm.identity_or_student_no}
                      onChange={(e) =>
                        setApplyForm((prev) => ({
                          ...prev,
                          identity_or_student_no: e.target.value,
                        }))
                      }
                      placeholder="Öğrenci veya TC No"
                      className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs sm:text-sm"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">
                    Bölüm / Adres *
                  </label>
                  <input
                    type="text"
                    required
                    value={applyForm.department_or_address}
                    onChange={(e) =>
                      setApplyForm((prev) => ({
                        ...prev,
                        department_or_address: e.target.value,
                      }))
                    }
                    placeholder="Bölüm veya açık adres"
                    className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs sm:text-sm"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">
                    Katılım Notu (İsteğe Bağlı)
                  </label>
                  <input
                    type="text"
                    value={applyForm.application_note}
                    onChange={(e) =>
                      setApplyForm((prev) => ({
                        ...prev,
                        application_note: e.target.value,
                      }))
                    }
                    placeholder="Yöneticiye notunuz..."
                    className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs sm:text-sm"
                  />
                </div>

                <div className="pt-2 flex items-center justify-end gap-2 border-t border-slate-100">
                  <button
                    type="button"
                    onClick={() => setLibraryModalMode(null)}
                    className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 cursor-pointer"
                  >
                    Kapat
                  </button>
                  <button
                    type="submit"
                    disabled={applySubmitting}
                    className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white text-xs font-extrabold cursor-pointer"
                  >
                    {applySubmitting ? 'Gönderiliyor...' : 'Katılma Başvurusu Gönder'}
                  </button>
                </div>
              </form>
            ) : (
              <form onSubmit={handleCreateLibraryRequestSubmit} className="p-6 space-y-4">
                <div>
                  <h3 className="text-base font-extrabold text-slate-900">
                    Yeni Kütüphane Oluşturma Talebi
                  </h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Kütüphane adı, açıklama ve başlangıç ceza/ödünç kurallarını belirleyerek Sistem Yöneticisi onayına gönderin.
                  </p>
                </div>

                {createLibSuccessBanner && (
                  <div className="p-4 rounded-2xl bg-amber-50 border-2 border-amber-400 text-amber-950 text-xs font-extrabold flex items-start gap-2.5">
                    <CheckCircle2 className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
                    <span>{createLibSuccessBanner}</span>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">
                    Kütüphane Adı *
                  </label>
                  <input
                    type="text"
                    required
                    value={createLibForm.name}
                    onChange={(e) =>
                      setCreateLibForm((prev) => ({ ...prev, name: e.target.value }))
                    }
                    placeholder="Örn: Merkez Araştırma Kütüphanesi"
                    className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm font-semibold"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">
                    Açıklama
                  </label>
                  <input
                    type="text"
                    value={createLibForm.description}
                    onChange={(e) =>
                      setCreateLibForm((prev) => ({ ...prev, description: e.target.value }))
                    }
                    placeholder="Kütüphane açıklaması..."
                    className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs sm:text-sm"
                  />
                </div>

                <div className="grid grid-cols-3 gap-2.5">
                  <div>
                    <label className="block text-[11px] font-bold text-slate-700 mb-1">
                      Günlük Ceza (TL)
                    </label>
                    <input
                      type="number"
                      step="0.5"
                      min="0"
                      required
                      value={createLibForm.daily_fine_amount}
                      onChange={(e) =>
                        setCreateLibForm((prev) => ({
                          ...prev,
                          daily_fine_amount: e.target.value,
                        }))
                      }
                      className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs sm:text-sm font-bold"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-bold text-slate-700 mb-1">
                      Ödünç Günü
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="365"
                      required
                      value={createLibForm.max_borrow_days}
                      onChange={(e) =>
                        setCreateLibForm((prev) => ({
                          ...prev,
                          max_borrow_days: e.target.value,
                        }))
                      }
                      className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs sm:text-sm font-bold"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-bold text-slate-700 mb-1">
                      Kitap Limiti
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="50"
                      required
                      value={createLibForm.max_books_per_user}
                      onChange={(e) =>
                        setCreateLibForm((prev) => ({
                          ...prev,
                          max_books_per_user: e.target.value,
                        }))
                      }
                      className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs sm:text-sm font-bold"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">
                    Ceza ve Ödünç Kuralları Metni
                  </label>
                  <textarea
                    rows={2}
                    value={createLibForm.penalty_rules_text}
                    onChange={(e) =>
                      setCreateLibForm((prev) => ({
                        ...prev,
                        penalty_rules_text: e.target.value,
                      }))
                    }
                    className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs"
                  />
                </div>

                <div className="pt-2 flex items-center justify-end gap-2 border-t border-slate-100">
                  <button
                    type="button"
                    onClick={() => setLibraryModalMode(null)}
                    className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 cursor-pointer"
                  >
                    Kapat
                  </button>
                  <button
                    type="submit"
                    disabled={createLibSubmitting}
                    className="px-5 py-2.5 rounded-xl bg-violet-700 hover:bg-violet-800 disabled:opacity-60 text-white text-xs font-extrabold cursor-pointer"
                  >
                    {createLibSubmitting ? 'Gönderiliyor...' : 'Onaya Gönder'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200/80 py-5 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-xs text-slate-400">
          © {new Date().getFullYear()} Kütüphane Yönetim Sistemi — FastAPI & React + Tailwind CSS
        </div>
      </footer>

      {/* Auth Modal */}
      {authModalMode && (
        <AuthModal
          initialMode={authModalMode}
          onClose={() => setAuthModalMode(null)}
          onSuccess={(loggedInUser) => {
            setUser(loggedInUser);
            if (Array.isArray(loggedInUser?.memberships)) {
              setMyMemberships(loggedInUser.memberships);
            }
            refreshCurrentUser(true);
          }}
          notify={notify}
        />
      )}

      {/* Book Detail Modal */}
      {selectedBook && (
        <BookDetailModal
          book={selectedBook}
          user={user}
          onClose={() => {
            setSelectedBook(null);
            fetchBooks();
            refreshCurrentUser(false);
            fetchMyActiveBorrowings();
          }}
          onOpenAuth={(mode) => setAuthModalMode(mode)}
          onBookUpdated={(freshBook) => {
            if (freshBook && freshBook.id) {
              setSelectedBook(freshBook);
            }
            fetchBooks();
            refreshCurrentUser(false);
            fetchMyActiveBorrowings();
          }}
          notify={notify}
        />
      )}

      {/* Giriş Sonrası Açılır Pencere (Modal): Ban / Hesap Kısıtlama & Gecikme / Kayıp-Hasar Tahsilat Uyarısı */}
      {accountAlertOpen && user && (
        <div className="fixed inset-0 z-[9990] flex items-center justify-center p-4 bg-slate-950/75 backdrop-blur-xs overflow-y-auto">
          <div className="bg-white rounded-3xl shadow-2xl border-2 border-rose-500 w-full max-w-xl overflow-hidden my-auto animate-in fade-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="bg-gradient-to-r from-rose-700 via-red-700 to-rose-800 text-white p-5 sm:p-6 flex items-start justify-between gap-4">
              <div className="flex items-start gap-3.5">
                <div className="w-12 h-12 rounded-2xl bg-white/15 backdrop-blur-xs flex items-center justify-center shrink-0 mt-0.5">
                  <ShieldAlert className="w-7 h-7 text-amber-300" />
                </div>
                <div>
                  <span className="inline-block px-2.5 py-0.5 rounded-full text-[11px] font-extrabold uppercase tracking-wider bg-amber-400 text-slate-950 mb-1.5">
                    ÖNEMLİ HESAP VE İŞLEM UYARISI
                  </span>
                  <h2 className="text-lg sm:text-xl font-extrabold leading-snug">
                    {user.is_banned
                      ? 'Hesabınız Yönetici Tarafından Kısıtlanmıştır!'
                      : (user.pending_penalty_approval_count || 0) > 0
                      ? 'Ödeme Onayı Bekleniyor / Borç Bildirimi'
                      : 'Gecikmiş Kitap veya Ödenmemiş Borç Bildirimi'}
                  </h2>
                  <p className="text-xs text-rose-100 mt-1">
                    Sayın {user.first_name} {user.last_name}, hesabınızla ilgili aşağıdaki durumu lütfen inceleyin.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setAccountAlertOpen(false)}
                className="p-1.5 rounded-xl text-white/80 hover:text-white hover:bg-white/15 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-5 sm:p-6 space-y-4 max-h-[75vh] overflow-y-auto">
              {/* 1. Yönetici Ban / Kısıtlama Kutusu */}
              {user.is_banned && (
                <div className="p-4 rounded-2xl bg-rose-50 border-2 border-rose-300 space-y-2">
                  <div className="flex items-center gap-2 text-rose-900 font-extrabold text-sm">
                    <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0" />
                    <span>Yönetici Kısıtlama (Ban) Kararı ve Sebebi:</span>
                  </div>
                  <div className="p-3.5 rounded-xl bg-white border border-rose-200 text-xs sm:text-sm font-bold text-slate-900 leading-relaxed">
                    "{user.ban_reason ||
                      'Kitap iadeniz ve gecikme/hasar ödemeniz yapılana kadar hesabınız yeni kitap ödünç almaya, rezervasyon yapmaya ve yorum yapmaya kapalı olacaktır.'}"
                  </div>
                  <p className="text-xs text-rose-800 leading-relaxed">
                    Bu kısıtlama aktif olduğu sürece <strong>yeni kitap ödünç alamaz</strong>,{' '}
                    <strong>rezervasyon sırasına giremez</strong> ve{' '}
                    <strong>kitaplara değerlendirme/yorum bırakamazsınız</strong>. Mevcut kitaplarınızı iade edebilir ve açık borçlarınızı ödeyebilirsiniz.
                  </p>
                </div>
              )}

              {/* 2. Yönetici Ödeme Onayı Bekleyen Cezalar Kutusu */}
              {Number(user.pending_penalty_approval_count || 0) > 0 && (
                <div className="p-4 rounded-2xl bg-amber-500/10 border-2 border-amber-400 space-y-2">
                  <div className="flex items-center gap-2 text-amber-950 font-extrabold text-sm">
                    <Clock className="w-5 h-5 text-amber-700 shrink-0" />
                    <span>Ödeme Yönetici Onayında Bekliyor ({user.pending_penalty_approval_count} İşlem)</span>
                  </div>
                  <div className="p-3.5 rounded-xl bg-white border border-amber-200 text-xs sm:text-sm font-semibold text-amber-950 leading-relaxed">
                    Ödemiş olduğunuz gecikme veya kayıp/hasar tazminat bedelinin yönetici tarafından onaylanması beklenmektedir. Yönetici ödemeyi aldığını onaylayana kadar yeni kitap ödünç alamaz veya rezervasyon oluşturamazsınız.
                  </div>
                </div>
              )}

              {/* 3. Gecikmiş Kitap & Gecikme / Kayıp / Hasar Tahsilat Ücreti Kutusu */}
              {(Number(user.overdue_books_count || 0) > 0 ||
                Number(user.unpaid_penalty_total || 0) > 0 ||
                (user.alert_items && user.alert_items.length > 0)) && (
                <div className="p-4 rounded-2xl bg-amber-50/90 border border-amber-300 space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 text-amber-950 font-extrabold text-sm">
                      <Banknote className="w-5 h-5 text-amber-700 shrink-0" />
                      <span>Gecikmiş Kitap & Tahsilat Ücreti Özeti</span>
                    </div>
                    <span className="px-3 py-1 rounded-full text-xs font-extrabold bg-rose-600 text-white">
                      Toplam Borç: {Number(user.unpaid_penalty_total || 0).toFixed(2)} TL
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-xs">
                    <div className="bg-white p-3 rounded-xl border border-amber-200">
                      <span className="text-slate-500 block text-[11px]">Gecikmiş Kitap</span>
                      <span className="text-base font-extrabold text-rose-700">
                        {user.overdue_books_count || 0} Adet
                      </span>
                    </div>
                    <div className="bg-white p-3 rounded-xl border border-amber-200">
                      <span className="text-slate-500 block text-[11px]">Gecikme Ücreti</span>
                      <span className="text-base font-extrabold text-amber-900">
                        {Number(user.unpaid_overdue_total || 0).toFixed(2)} TL
                      </span>
                    </div>
                    <div className="bg-white p-3 rounded-xl border border-amber-200">
                      <span className="text-slate-500 block text-[11px]">Kayıp / Hasar Ücreti</span>
                      <span className="text-base font-extrabold text-rose-800">
                        {Number(user.unpaid_damage_loss_total || 0).toFixed(2)} TL
                      </span>
                    </div>
                  </div>

                  {/* İlgili Kitapların Listesi */}
                  {user.alert_items && user.alert_items.length > 0 && (
                    <div className="space-y-2 pt-1">
                      <span className="text-[11px] font-bold uppercase tracking-wider text-amber-900 block">
                        İşlem / Ödeme Bekleyen Kayıtlarınız ({user.alert_items.length})
                      </span>
                      <div className="space-y-1.5 max-h-44 overflow-y-auto pr-1">
                        {user.alert_items.map((item) => (
                          <div
                            key={item.borrowing_id}
                            className="bg-white p-3 rounded-xl border border-amber-200 flex items-center justify-between gap-2 text-xs"
                          >
                            <div>
                              <span className="font-bold text-slate-900 block">
                                {item.book_title}
                              </span>
                              <div className="flex flex-wrap items-center gap-1.5 mt-0.5 text-[11px] text-slate-500">
                                <span>Son Teslim: {item.due_date}</span>
                                {item.overdue_days > 0 && (
                                  <span className="px-1.5 py-0.2 rounded bg-rose-100 text-rose-800 font-bold">
                                    {item.overdue_days} Gün Gecikme
                                  </span>
                                )}
                                {item.return_condition === 'LOST' && (
                                  <span className="px-1.5 py-0.2 rounded bg-rose-600 text-white font-bold">
                                    Kayıp Kitap Tazminatı
                                  </span>
                                )}
                                {item.return_condition === 'DAMAGED' && (
                                  <span className="px-1.5 py-0.2 rounded bg-amber-200 text-amber-950 font-bold">
                                    Hasarlı Kitap Tazminatı
                                  </span>
                                )}
                                {item.penalty_payment_status === 'PENDING_APPROVAL' && (
                                  <span className="px-1.5 py-0.2 rounded bg-amber-300 text-amber-950 font-extrabold border border-amber-400">
                                    Ödeme Onayı Bekliyor
                                  </span>
                                )}
                              </div>
                            </div>
                            <span className="font-extrabold text-rose-700 shrink-0">
                              {Number(item.penalty_amount || 0).toFixed(2)} TL
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <p className="text-xs text-amber-950 leading-relaxed">
                    Kütüphane kuralları gereği; geciktirdiğiniz kitabı iade edene ve oluşan{' '}
                    <strong>gecikme ücretini</strong> veya{' '}
                    <strong>hasar / kayıp tahsilat ücretini</strong> ödeyene kadar yeni kitap ödünç alamaz ve rezervasyon yapamazsınız.
                  </p>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-5 py-4 bg-slate-50 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-end gap-2.5">
              <button
                type="button"
                onClick={() => setAccountAlertOpen(false)}
                className="w-full sm:w-auto px-4 py-2.5 rounded-xl text-xs font-bold bg-slate-200 hover:bg-slate-300 text-slate-800 transition-colors cursor-pointer"
              >
                Anladım, Kapat
              </button>
              <button
                type="button"
                onClick={() => {
                  setAccountAlertOpen(false);
                  setActiveTab('mylibrary');
                }}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-xs font-extrabold bg-rose-600 hover:bg-rose-700 text-white shadow-sm transition-colors cursor-pointer"
              >
                <Banknote className="w-4 h-4" />
                Kitaplarım & Borç Ödeme Ekranına Git
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Yönetici Açılır Pencere (Modal): Onay Bekleyen Ödemeler & İade/Ödünç Onayı Uyarısı */}
      {adminAlertOpen && user?.roles?.includes('ADMIN') && (
        <div className="fixed inset-0 z-[9990] flex items-center justify-center p-4 bg-slate-950/75 backdrop-blur-xs overflow-y-auto">
          <div className="bg-white rounded-3xl shadow-2xl border-2 border-amber-500 w-full max-w-xl overflow-hidden my-auto animate-in fade-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="bg-gradient-to-r from-amber-600 via-orange-600 to-amber-700 text-white p-5 sm:p-6 flex items-start justify-between gap-4">
              <div className="flex items-start gap-3.5">
                <div className="w-12 h-12 rounded-2xl bg-white/15 backdrop-blur-xs flex items-center justify-center shrink-0 mt-0.5">
                  <ShieldCheck className="w-7 h-7 text-amber-200" />
                </div>
                <div>
                  <span className="inline-block px-2.5 py-0.5 rounded-full text-[11px] font-extrabold uppercase tracking-wider bg-white text-amber-950 mb-1.5">
                    YETKİLİ YÖNETİCİ ONAY VE İŞ AKIŞI UYARISI
                  </span>
                  <h2 className="text-lg sm:text-xl font-extrabold leading-snug">
                    Bekleyen Yönetici Onayları Bulunmaktadır!
                  </h2>
                  <p className="text-xs text-amber-100 mt-1">
                    Sayın {user.first_name} {user.last_name}, onay ve aksiyonunuzu bekleyen işlemler bulunmaktadır.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setAdminAlertOpen(false)}
                className="p-1.5 rounded-xl text-white/80 hover:text-white hover:bg-white/15 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-5 sm:p-6 space-y-3.5 max-h-[75vh] overflow-y-auto">
              {/* 1. Onay Bekleyen Ödemeler */}
              {Number(notifications?.pending_penalty_approvals || 0) > 0 && (
                <div className="p-4 rounded-2xl bg-purple-50/90 border border-purple-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-purple-950 font-bold text-sm">
                      <CreditCard className="w-4 h-4 text-purple-700" />
                      <span>Onay Bekleyen Ceza / Tazminat Ödemeleri</span>
                      <span className="px-2 py-0.5 rounded-full text-xs font-black bg-purple-600 text-white">
                        {notifications.pending_penalty_approvals} Adet
                      </span>
                    </div>
                    <p className="text-xs text-purple-900 leading-relaxed">
                      Kullanıcılar ceza veya hasar/kayıp tazminatını ödedi. Yönetici onayı verilene kadar yeni ödünç ve rezervasyon hakları kısıtlıdır.
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setAdminAlertOpen(false);
                      setAdminNavTarget({ subTab: 'penalties', filter: 'PENDING_APPROVAL' });
                      setActiveTab('admin');
                    }}
                    className="shrink-0 px-3.5 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold shadow-2xs transition-colors cursor-pointer"
                  >
                    Ödemeleri Onayla &rarr;
                  </button>
                </div>
              )}

              {/* 2. İade Onayı Bekleyen Kitaplar */}
              {Number(notifications?.pending_return_approvals || 0) > 0 && (
                <div className="p-4 rounded-2xl bg-amber-50/90 border border-amber-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-amber-950 font-bold text-sm">
                      <RotateCcw className="w-4 h-4 text-amber-700" />
                      <span>İade Onayı Bekleyen Kitaplar</span>
                      <span className="px-2 py-0.5 rounded-full text-xs font-black bg-amber-600 text-white">
                        {notifications.pending_return_approvals} Adet
                      </span>
                    </div>
                    <p className="text-xs text-amber-900 leading-relaxed">
                      Kullanıcılar kitapları iade etti. Kitapların fiziksel durumunu kontrol edip (sağlam/hasarlı/kayıp) teslim almanız bekleniyor.
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setAdminAlertOpen(false);
                      setAdminNavTarget({ subTab: 'workflow', filter: 'RETURNS' });
                      setActiveTab('admin');
                    }}
                    className="shrink-0 px-3.5 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold shadow-2xs transition-colors cursor-pointer"
                  >
                    İade Kuyruğuna Git &rarr;
                  </button>
                </div>
              )}

              {/* 3. Ödünç Alma Talepleri */}
              {Number(notifications?.pending_borrow_approvals || 0) > 0 && (
                <div className="p-4 rounded-2xl bg-blue-50/90 border border-blue-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-blue-950 font-bold text-sm">
                      <BookOpen className="w-4 h-4 text-blue-700" />
                      <span>Ödünç Alma Talepleri</span>
                      <span className="px-2 py-0.5 rounded-full text-xs font-black bg-blue-600 text-white">
                        {notifications.pending_borrow_approvals} Adet
                      </span>
                    </div>
                    <p className="text-xs text-blue-900 leading-relaxed">
                      Kullanıcılar ödünç talebinde bulundu. Kitabın rafdan teslim edilip teslimat onayının verilmesi bekleniyor.
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setAdminAlertOpen(false);
                      setAdminNavTarget({ subTab: 'workflow', filter: 'BORROWS' });
                      setActiveTab('admin');
                    }}
                    className="shrink-0 px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow-2xs transition-colors cursor-pointer"
                  >
                    Ödünç Kuyruğuna Git &rarr;
                  </button>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-5 py-4 bg-slate-50 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-end gap-2.5">
              <button
                type="button"
                onClick={() => setAdminAlertOpen(false)}
                className="w-full sm:w-auto px-4 py-2.5 rounded-xl text-xs font-bold bg-slate-200 hover:bg-slate-300 text-slate-800 transition-colors cursor-pointer"
              >
                Anladım, Kapat
              </button>
              <button
                type="button"
                onClick={() => {
                  setAdminAlertOpen(false);
                  setActiveTab('admin');
                }}
                className="w-full sm:w-auto px-4 py-2.5 rounded-xl text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white transition-colors cursor-pointer flex items-center justify-center gap-1.5"
              >
                <ShieldCheck className="w-4 h-4" />
                Admin Paneline Git
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Yüksek Öncelikli ve Net Görünürlüklü Toast Bildirimleri (Tüm pencerelerin ve modalların en üstünde) */}
      <div className="fixed bottom-5 right-5 z-[9999] flex flex-col gap-2.5 max-w-sm w-full px-4 sm:px-0 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-start gap-3 p-4 rounded-2xl shadow-2xl border transition-all animate-in fade-in slide-in-from-bottom-3 duration-200 ${
              t.type === 'success'
                ? 'bg-emerald-600 text-white border-emerald-400 ring-4 ring-emerald-500/25'
                : t.type === 'error'
                ? 'bg-rose-600 text-white border-rose-400 ring-4 ring-rose-500/25'
                : 'bg-indigo-600 text-white border-indigo-400 ring-4 ring-indigo-500/25'
            }`}
          >
            {t.type === 'success' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-100 shrink-0 mt-0.5" />
            ) : t.type === 'error' ? (
              <AlertCircle className="w-5 h-5 text-rose-100 shrink-0 mt-0.5" />
            ) : (
              <Info className="w-5 h-5 text-indigo-100 shrink-0 mt-0.5" />
            )}
            <div className="flex-1 text-xs sm:text-sm font-semibold leading-snug drop-shadow-2xs">
              {t.message}
            </div>
            <button
              onClick={() =>
                setToasts((prev) => prev.filter((item) => item.id !== t.id))
              }
              className="text-white/80 hover:text-white hover:bg-white/10 p-0.5 rounded-lg transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

