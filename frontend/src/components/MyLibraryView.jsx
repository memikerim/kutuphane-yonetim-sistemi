import React, { useState, useEffect } from 'react';
import {
  BookOpen,
  Clock,
  CheckCircle2,
  RotateCcw,
  Calendar,
  BookmarkCheck,
  RefreshCw,
  AlertCircle,
  Trash2,
  Users,
  Banknote,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  X,
} from 'lucide-react';
import { api } from '../api';

const BORROWINGS_PER_PAGE = 6;

function formatRemainingCountdown(expiresAt, nowMs) {
  if (!expiresAt) return null;
  const targetMs = new Date(expiresAt).getTime();
  const diffSec = Math.max(0, Math.floor((targetMs - nowMs) / 1000));
  const hours = Math.floor(diffSec / 3600);
  const minutes = Math.floor((diffSec % 3600) / 60);
  const seconds = diffSec % 60;
  return {
    diffSec,
    text: `${hours} saat ${String(minutes).padStart(2, '0')} dk ${String(seconds).padStart(2, '0')} sn`,
  };
}

export default function MyLibraryView({ notify, onSelectBook, onCatalogChanged }) {
  const [borrowings, setBorrowings] = useState([]);
  const [reservations, setReservations] = useState([]);
  const [bookMap, setBookMap] = useState({});
  const [loading, setLoading] = useState(true);
  const [returningId, setReturningId] = useState(null);
  const [cancellingBorrowId, setCancellingBorrowId] = useState(null);
  const [payingPenaltyId, setPayingPenaltyId] = useState(null);
  const [borrowingResId, setBorrowingResId] = useState(null);
  const [cancellingResId, setCancellingResId] = useState(null);
  const [subTab, setSubTab] = useState('borrowings');
  const [borrowingFilter, setBorrowingFilter] = useState('active_pending'); // 'active_pending' | 'history' | 'all'
  const [borrowingPage, setBorrowingPage] = useState(1);
  const [nowMs, setNowMs] = useState(Date.now());

  // İade & Fiziksel Durum Kontrol Modalı State'leri
  const [returnModalItem, setReturnModalItem] = useState(null);
  const [returnCondition, setReturnCondition] = useState('GOOD'); // 'GOOD' | 'DAMAGED' | 'LOST'
  const [returnNotes, setReturnNotes] = useState('');

  const fetchAll = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [borrowList, resList, booksResp] = await Promise.all([
        api.getMyBorrowings(),
        api.getMyReservations(),
        api.getBooks({ page: 1, limit: 100 }),
      ]);

      const map = {};
      if (booksResp?.items) {
        booksResp.items.forEach((b) => {
          map[b.id] = b;
        });
      }

      // Fetch any missing book details individually
      const allBookIds = new Set([
        ...(borrowList || []).map((b) => b.book_id),
        ...(resList || []).map((r) => r.book_id),
      ]);

      for (const bId of allBookIds) {
        if (!map[bId]) {
          try {
            const singleBook = await api.getBook(bId);
            if (singleBook) map[bId] = singleBook;
          } catch {
            // ignore if deleted
          }
        }
      }

      setBookMap(map);
      setBorrowings(borrowList || []);
      setReservations(resList || []);
    } catch (err) {
      if (!silent) {
        notify(err.message || 'Bilgileriniz yüklenirken hata oluştu', 'error');
      }
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll(false);
    const pollTimer = setInterval(() => {
      fetchAll(true);
    }, 10000);
    return () => clearInterval(pollTimer);
  }, []);

  // Live 1-second ticker for 24-hour reservation countdown & queue transition
  useEffect(() => {
    const timer = setInterval(() => {
      const current = Date.now();
      setNowMs(current);
      const anyJustTransitioned = reservations.some(
        (r) =>
          (r.expires_at && new Date(r.expires_at).getTime() <= current) ||
          (r.turn_starts_at && new Date(r.turn_starts_at).getTime() <= current)
      );
      if (anyJustTransitioned) {
        fetchAll(true);
        if (onCatalogChanged) onCatalogChanged();
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [reservations]);

  const openReturnModal = (item) => {
    setReturnModalItem(item);
    setReturnCondition('GOOD');
    setReturnNotes('');
  };

  const handleConfirmReturnSubmit = async (e) => {
    e.preventDefault();
    if (!returnModalItem) return;
    const borrowingId = returnModalItem.id;
    setReturningId(borrowingId);
    try {
      await api.returnBook(borrowingId, {
        request_approval: true,
        return_condition: returnCondition,
        return_notes: returnNotes.trim() || undefined,
      });
      notify(
        returnCondition === 'GOOD'
          ? 'İade talebiniz oluşturuldu! Görevli (Admin) fiziksel kontrol onayından sonra kitap rafa eklenecektir.'
          : returnCondition === 'DAMAGED'
          ? 'Hasarlı kitap iade bildiriminiz görevli onay kuyruğuna iletildi.'
          : 'Kayıp kitap bildiriminiz görevli onay kuyruğuna iletildi.',
        'info'
      );
      setReturnModalItem(null);
      await fetchAll();
      if (onCatalogChanged) onCatalogChanged();
    } catch (err) {
      notify(err.message || 'İade talebi oluşturulamadı', 'error');
    } finally {
      setReturningId(null);
    }
  };

  const handleCancelBorrowRequest = async (borrowingId) => {
    if (
      !window.confirm(
        'Henüz görevli tarafından onaylanmamış bu ödünç talebini iptal etmek istediğinize emin misiniz? (Ayrılan stok rafa geri eklenecektir)'
      )
    ) {
      return;
    }
    setCancellingBorrowId(borrowingId);
    try {
      await api.cancelBorrowRequest(borrowingId);
      notify('Ödünç talebiniz iptal edildi ve ayrılan stok (+1) rafa geri eklendi.', 'info');
      await fetchAll();
      if (onCatalogChanged) onCatalogChanged();
    } catch (err) {
      notify(err.message || 'Ödünç talebi iptal edilemedi', 'error');
    } finally {
      setCancellingBorrowId(null);
    }
  };

  const handlePayPenalty = async (borrowingId, amount) => {
    if (
      !window.confirm(
        `${amount} TL tutarındaki ceza/tazminat borcunu ödemek istiyor musunuz?\n\nNot: Ödemeniz görevli onayına iletilecek ve yönetici ödemeyi aldığını onaylayana kadar yeni kitap ödünç alma ve rezervasyon işlemleriniz kısıtlı kalacaktır.`
      )
    ) {
      return;
    }
    setPayingPenaltyId(borrowingId);
    try {
      await api.payPenalty(borrowingId);
      notify(
        `${amount} TL tutarındaki ödemeniz iletildi! Yönetici ödemeyi aldığını onaylayana kadar yeni kitap ödünç alma ve rezervasyon işlemleriniz kapalı kalacaktır.`,
        'info'
      );
      await fetchAll();
      if (onCatalogChanged) onCatalogChanged();
    } catch (err) {
      notify(err.message || 'Ceza ödeme işlemi başarısız', 'error');
    } finally {
      setPayingPenaltyId(null);
    }
  };

  const handleBorrowReservedBook = async (res) => {
    const bookTitle = bookMap[res.book_id]?.title || 'Kitap';
    if (
      !window.confirm(
        `"${bookTitle}" için rezerve sıranızı kullanarak ödünç talebi oluşturmak istiyor musunuz?`
      )
    ) {
      return;
    }
    setBorrowingResId(res.id);
    try {
      const d = new Date();
      d.setDate(d.getDate() + 14);
      const dueDateStr = d.toISOString().split('T')[0];

      await api.borrowBook({
        book_id: res.book_id,
        due_date: dueDateStr,
        request_approval: true,
        notes: 'Rezervasyon sırasından ödünç talep edildi',
      });
      notify(
        `"${bookTitle}" için ödünç talebiniz oluşturuldu ve görevli onay kuyruğuna iletildi!`,
        'success'
      );
      await fetchAll();
      if (onCatalogChanged) onCatalogChanged();
    } catch (err) {
      notify(err.message || 'Ödünç alma işlemi başarısız', 'error');
    } finally {
      setBorrowingResId(null);
    }
  };

  const handleCancelReservation = async (resId) => {
    if (!window.confirm('Bu rezervasyonu iptal edip sıradan çıkmak istediğinize emin misiniz?')) {
      return;
    }
    setCancellingResId(resId);
    try {
      await api.cancelReservation(resId);
      notify('Rezervasyonunuz iptal edildi ve listeden kaldırıldı.', 'info');
      await fetchAll();
      if (onCatalogChanged) onCatalogChanged();
    } catch (err) {
      notify(err.message || 'Rezervasyon iptal edilemedi', 'error');
    } finally {
      setCancellingResId(null);
    }
  };

  const activeBorrowingsCount = borrowings.filter(
    (b) => b.status === 'ACTIVE' || b.status === 'OVERDUE'
  ).length;
  const pendingReservationsCount = reservations.filter((r) => r.status === 'PENDING').length;

  const activeAndPendingList = borrowings.filter(
    (b) =>
      b.status !== 'RETURNED' ||
      ((b.penalty_amount || 0) > 0 && !b.is_penalty_paid)
  );
  const returnedHistoryList = borrowings.filter(
    (b) =>
      b.status === 'RETURNED' &&
      !((b.penalty_amount || 0) > 0 && !b.is_penalty_paid)
  );

  const filteredBorrowings =
    borrowingFilter === 'active_pending'
      ? activeAndPendingList
      : borrowingFilter === 'history'
      ? returnedHistoryList
      : borrowings;

  const totalBorrowingPages = Math.max(
    1,
    Math.ceil(filteredBorrowings.length / BORROWINGS_PER_PAGE)
  );
  const safeBorrowingPage = Math.min(borrowingPage, totalBorrowingPages);
  const paginatedBorrowings = filteredBorrowings.slice(
    (safeBorrowingPage - 1) * BORROWINGS_PER_PAGE,
    safeBorrowingPage * BORROWINGS_PER_PAGE
  );

  const overdueActiveCount = borrowings.filter(
    (b) =>
      b.status !== 'RETURNED' &&
      b.approval_status !== 'PENDING_BORROW' &&
      (b.status === 'OVERDUE' || (b.overdue_days || 0) > 0)
  ).length;

  const unpaidReturnedCount = borrowings.filter(
    (b) => b.status === 'RETURNED' && (b.penalty_amount || 0) > 0 && !b.is_penalty_paid
  ).length;

  const totalActiveDebt = borrowings.reduce((sum, b) => {
    if (b.status === 'RETURNED') {
      if ((b.penalty_amount || 0) > 0 && !b.is_penalty_paid) {
        return sum + Number(b.penalty_amount || 0);
      }
      return sum;
    }
    if (b.status === 'OVERDUE' || (b.overdue_days || 0) > 0) {
      return sum + Number(b.penalty_amount || 0);
    }
    return sum;
  }, 0);

  return (
    <div className="space-y-6">
      {/* Overdue & Active Penalty Debt Alert Banner */}
      {(totalActiveDebt > 0 || overdueActiveCount > 0) && (
        <div className="bg-gradient-to-r from-rose-600 via-rose-700 to-red-800 text-white rounded-2xl p-5 sm:p-6 shadow-lg border border-rose-500 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="w-11 h-11 rounded-2xl bg-white/15 backdrop-blur-xs flex items-center justify-center shrink-0 mt-0.5">
              <AlertTriangle className="w-6 h-6 text-amber-300" />
            </div>
            <div>
              <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-white/20 text-rose-100 mb-1.5">
                GECİKME VE CEZA UYARISI (GÜNLÜK 10 TL)
              </div>
              <h2 className="text-lg sm:text-xl font-extrabold">
                Toplam Aktif Gecikme Borcunuz: {totalActiveDebt.toFixed(2)} TL
              </h2>
              <p className="text-xs sm:text-sm text-rose-100 mt-1 leading-relaxed">
                Ödenmemiş gecikme cezanız ({unpaidReturnedCount} adet) veya süresi geçmiş kitabınız ({overdueActiveCount} adet) bulunduğu için yeni kitap ödünç alamaz ve rezervasyon yapamazsınız. Lütfen geciken kitapları iade edin ve oluşan cezaları ödeyin.
              </p>
            </div>
          </div>
          <div className="bg-white/10 backdrop-blur-xs border border-white/20 rounded-2xl px-4 py-3 text-center shrink-0">
            <span className="block text-[11px] uppercase tracking-wider text-rose-200 font-bold">
              Güncel Toplam Borç
            </span>
            <span className="text-2xl font-extrabold text-white">
              {totalActiveDebt.toFixed(2)} TL
            </span>
          </div>
        </div>
      )}

      {/* Header Banner */}
      <div className="bg-white rounded-2xl p-5 sm:p-6 border border-slate-200/80 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900 flex items-center gap-2.5">
            <BookmarkCheck className="w-6 h-6 text-indigo-600" />
            Kitaplarım & Rezervasyonlarım
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Ödünç aldığınız kitapları görüntüleyip tek tıkla iade edebilir, rezervasyon sıranızı ve 24 saatlik kalan sürenizi takip edebilirsiniz.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5 self-start sm:self-auto">
          <div
            className={`px-3.5 py-2 rounded-xl text-xs font-bold border ${
              activeBorrowingsCount >= 3
                ? 'bg-rose-50 text-rose-700 border-rose-200'
                : 'bg-indigo-50 text-indigo-700 border-indigo-200'
            }`}
          >
            Aktif Ödünç Kotası: {activeBorrowingsCount} / 3 Kitap
          </div>
          <button
            onClick={fetchAll}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Listeyi Yenile
          </button>
        </div>
      </div>

      {/* Sub-navigation Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-3">
        <button
          onClick={() => setSubTab('borrowings')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all cursor-pointer ${
            subTab === 'borrowings'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
          }`}
        >
          <BookOpen className="w-4 h-4" />
          Ödünç Aldığım Kitaplar ({borrowings.length})
          {activeBorrowingsCount > 0 && (
            <span
              className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${
                subTab === 'borrowings'
                  ? 'bg-white/20 text-white'
                  : 'bg-indigo-100 text-indigo-700'
              }`}
            >
              {activeBorrowingsCount} Aktif
            </span>
          )}
        </button>

        <button
          onClick={() => setSubTab('reservations')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all cursor-pointer ${
            subTab === 'reservations'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
          }`}
        >
          <Clock className="w-4 h-4" />
          Rezervasyonlarım ({reservations.length})
          {pendingReservationsCount > 0 && (
            <span
              className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${
                subTab === 'reservations'
                  ? 'bg-white/20 text-white'
                  : 'bg-amber-100 text-amber-800'
              }`}
            >
              {pendingReservationsCount} Bekleyen
            </span>
          )}
        </button>
      </div>

      {/* Content */}
      {loading ? (
        <div className="bg-white rounded-2xl p-12 text-center border border-slate-200">
          <div className="w-8 h-8 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-slate-500">Kayıtlarınız yükleniyor...</p>
        </div>
      ) : subTab === 'borrowings' ? (
        <div className="space-y-4">
          {/* Sub-filter bar to prevent endless vertical list */}
          <div className="bg-white rounded-2xl p-3 border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-1.5">
              <button
                onClick={() => {
                  setBorrowingFilter('active_pending');
                  setBorrowingPage(1);
                }}
                className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                  borrowingFilter === 'active_pending'
                    ? 'bg-indigo-600 text-white shadow-xs'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                Aktif, Onay Bekleyen & Borçlu ({activeAndPendingList.length})
              </button>
              <button
                onClick={() => {
                  setBorrowingFilter('history');
                  setBorrowingPage(1);
                }}
                className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                  borrowingFilter === 'history'
                    ? 'bg-indigo-600 text-white shadow-xs'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                İade Geçmişim / Okuduklarım ({returnedHistoryList.length})
              </button>
              <button
                onClick={() => {
                  setBorrowingFilter('all');
                  setBorrowingPage(1);
                }}
                className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                  borrowingFilter === 'all'
                    ? 'bg-indigo-600 text-white shadow-xs'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                Tümü ({borrowings.length})
              </button>
            </div>
            <span className="text-xs text-slate-500 font-medium px-1">
              Gösterilen: <strong className="text-slate-800">{filteredBorrowings.length}</strong> kayıt (Sayfa {safeBorrowingPage}/{totalBorrowingPages})
            </span>
          </div>

          {filteredBorrowings.length === 0 ? (
            <div className="bg-white rounded-2xl p-10 text-center border border-dashed border-slate-300">
              <BookOpen className="w-10 h-10 text-slate-300 mx-auto mb-2" />
              <h3 className="text-base font-bold text-slate-800">
                {borrowingFilter === 'active_pending'
                  ? 'Aktif, onay bekleyen veya borçlu ödünç kaydınız bulunmuyor'
                  : borrowingFilter === 'history'
                  ? 'Henüz tamamlanmış iade geçmişiniz bulunmuyor'
                  : 'Henüz ödünç aldığınız bir kitap yok'}
              </h3>
              <p className="text-xs text-slate-500 mt-1">
                {borrowingFilter === 'active_pending' && returnedHistoryList.length > 0
                  ? `Geçmişte iade ettiğiniz ${returnedHistoryList.length} kitabı görmek için "İade Geçmişim / Okuduklarım" sekmesine geçebilirsiniz.`
                  : 'Katalog vitrininden istediğiniz kitabı seçip ödünç talebi oluşturabilirsiniz.'}
              </p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {paginatedBorrowings.map((item) => {
                  const book = bookMap[item.book_id];
                  const isReturned = item.status === 'RETURNED';
                  const approvalStatus = item.approval_status || 'APPROVED';
                  const isPendingBorrow = !isReturned && approvalStatus === 'PENDING_BORROW';
                  const isPendingReturn = !isReturned && approvalStatus === 'PENDING_RETURN';
                  const isRejected = isReturned && approvalStatus === 'REJECTED';
                  const returnCond = item.return_condition || 'GOOD';
                  const damagePenalty = Number(item.damage_penalty || 0);
                  const overdueDays = Number(item.overdue_days || 0);
                  const penaltyAmount = Number(item.penalty_amount || 0);
                  const isOverdue =
                    !isReturned &&
                    !isPendingBorrow &&
                    (item.status === 'OVERDUE' ||
                      overdueDays > 0 ||
                      new Date(item.due_date) < new Date(new Date().toDateString()));
                  const hasUnpaidPenalty = isReturned && penaltyAmount > 0 && !item.is_penalty_paid;

                  return (
                    <div
                      key={item.id}
                      className={`bg-white rounded-2xl p-5 border shadow-2xs flex flex-col justify-between gap-4 transition-all ${
                        isOverdue || hasUnpaidPenalty
                          ? 'border-rose-300 ring-1 ring-rose-100'
                          : isPendingBorrow || isPendingReturn
                          ? 'border-amber-300 ring-1 ring-amber-100'
                          : 'border-slate-200/90 hover:border-indigo-200'
                      }`}
                    >
                      <div className="space-y-3">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <button
                              onClick={() => book && onSelectBook(book)}
                              className="text-left font-bold text-base text-slate-900 hover:text-indigo-600 transition-colors cursor-pointer"
                            >
                              {book ? book.title : item.book_title || `Kitap ID: ${item.book_id.slice(0, 8)}...`}
                            </button>
                            {(book || item.book_isbn) && (
                              <p className="text-xs text-slate-500 mt-0.5">
                                ISBN: {book ? book.isbn : item.book_isbn}
                                {book?.authors?.length > 0 &&
                                  ` • ${book.authors.map((a) => `${a.first_name} ${a.last_name}`).join(', ')}`}
                              </p>
                            )}
                          </div>

                          <div className="flex flex-col items-end gap-1 shrink-0">
                            {isRejected ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-slate-200 text-slate-700 border border-slate-300">
                                <X className="w-3.5 h-3.5 text-slate-600" />
                                Talep İptal / Red
                              </span>
                            ) : isPendingBorrow ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-300">
                                <Clock className="w-3.5 h-3.5 text-amber-600 animate-pulse" />
                                Ödünç Onayı Bekliyor
                              </span>
                            ) : isPendingReturn ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-indigo-100 text-indigo-900 border border-indigo-300">
                                <ShieldCheck className="w-3.5 h-3.5 text-indigo-600 animate-pulse" />
                                İade Kontrolünde
                              </span>
                            ) : isReturned ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-slate-100 text-slate-700 border border-slate-300">
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                                İade Edildi
                              </span>
                            ) : isOverdue ? (
                              <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-extrabold bg-rose-600 text-white shadow-xs">
                                <AlertCircle className="w-3.5 h-3.5" />
                                GECİKMİŞ ({overdueDays} Gün)
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                                <Clock className="w-3.5 h-3.5" />
                                Aktif Ödünç
                              </span>
                            )}

                            {returnCond === 'DAMAGED' && (
                              <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-300">
                                Hasarlı İade ({damagePenalty > 0 ? `+${damagePenalty} TL` : 'Raporlu'})
                              </span>
                            )}
                            {returnCond === 'LOST' && (
                              <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-rose-100 text-rose-900 border border-rose-300">
                                Kayıp Kitap ({damagePenalty > 0 ? `+${damagePenalty} TL` : 'Raporlu'})
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-2 border-t border-slate-100 text-xs">
                          <div className="bg-slate-50 p-2.5 rounded-xl">
                            <span className="text-slate-400 block text-[11px]">Talep / Ödünç Tarihi</span>
                            <span className="font-semibold text-slate-700 flex items-center gap-1 mt-0.5">
                              <Calendar className="w-3.5 h-3.5 text-indigo-500" />
                              {item.borrow_date}
                            </span>
                          </div>
                          <div
                            className={`p-2.5 rounded-xl ${
                              isOverdue ? 'bg-rose-50 border border-rose-200' : 'bg-slate-50'
                            }`}
                          >
                            <span
                              className={`block text-[11px] ${
                                isOverdue ? 'text-rose-600 font-bold' : 'text-slate-400'
                              }`}
                            >
                              Son Teslim Tarihi
                            </span>
                            <span
                              className={`font-semibold flex items-center gap-1 mt-0.5 ${
                                isOverdue ? 'text-rose-800' : 'text-slate-700'
                              }`}
                            >
                              <Calendar
                                className={`w-3.5 h-3.5 ${
                                  isOverdue ? 'text-rose-600' : 'text-amber-500'
                                }`}
                              />
                              {item.due_date}
                            </span>
                          </div>
                          {item.return_date && (
                            <div className="bg-emerald-50/70 p-2.5 rounded-xl col-span-2 sm:col-span-1">
                              <span className="text-emerald-600 block text-[11px]">İade / Kapanış</span>
                              <span className="font-semibold text-emerald-800 flex items-center gap-1 mt-0.5">
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                                {item.return_date}
                              </span>
                            </div>
                          )}
                        </div>

                        {/* Workflow Status Info Banners */}
                        {isPendingBorrow && (
                          <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-900">
                            <span className="font-bold block">
                              Görevli (Kütüphaneci) Teslim Onayı Bekleniyor
                            </span>
                            <span className="text-[11px] text-amber-800">
                              Kitap stoğu sizin için ayrılmıştır (-1). Görevli onayladığında ödünç süreniz başlar. İsterseniz talebi iptal edebilirsiniz.
                            </span>
                          </div>
                        )}

                        {isPendingReturn && (
                          <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-3 text-xs text-indigo-900">
                            <span className="font-bold block">
                              İade & Fiziksel Durum Kontrolü Bekleniyor (Bildirim:{' '}
                              {returnCond === 'GOOD'
                                ? 'Sağlam'
                                : returnCond === 'DAMAGED'
                                ? 'Hasarlı'
                                : 'Kayıp'}
                              )
                            </span>
                            <span className="text-[11px] text-indigo-800">
                              Görevli kitabın fiziksel durumunu kontrol edip onayladığında iade işleminiz tamamlanacaktır.
                            </span>
                          </div>
                        )}

                        {(item.return_notes || item.admin_notes) && (
                          <div className="bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-[11px] text-slate-600 space-y-1">
                            {item.return_notes && (
                              <div>
                                <strong className="text-slate-800">Notunuz:</strong> {item.return_notes}
                              </div>
                            )}
                            {item.admin_notes && (
                              <div>
                                <strong className="text-indigo-700">Görevli Notu:</strong> {item.admin_notes}
                              </div>
                            )}
                          </div>
                        )}

                        {/* Overdue / Penalty Info Banner inside Card */}
                        {isOverdue && (
                          <div className="bg-rose-50 border border-rose-200 rounded-xl p-3 flex items-center justify-between gap-2 text-xs">
                            <div className="text-rose-800">
                              <span className="font-bold block">
                                Gecikme Süresi: {overdueDays} Gün (Günlük 10 TL)
                              </span>
                              <span className="text-[11px] text-rose-600">
                                Kitabı iade ettiğinizde ceza tutarı hesabınıza yansıtılacaktır.
                              </span>
                            </div>
                            <span className="px-2.5 py-1 rounded-lg bg-rose-600 text-white font-extrabold text-xs shrink-0">
                              {penaltyAmount.toFixed(2)} TL
                            </span>
                          </div>
                        )}

                        {isReturned && penaltyAmount > 0 && (
                          <div
                            className={`rounded-xl p-3 border flex items-center justify-between gap-2 text-xs ${
                              item.is_penalty_paid
                                ? 'bg-emerald-50/80 border-emerald-200 text-emerald-900'
                                : item.penalty_payment_status === 'PENDING_APPROVAL'
                                ? 'bg-purple-50 border-purple-300 text-purple-950'
                                : 'bg-amber-50 border-amber-300 text-amber-950'
                            }`}
                          >
                            <div>
                              <span className="font-bold block">
                                Toplam Ceza / Tazminat: {penaltyAmount.toFixed(2)} TL
                                {overdueDays > 0 ? ` (${overdueDays} Gün Gecikme)` : ''}
                                {damagePenalty > 0
                                  ? ` (${returnCond === 'LOST' ? 'Kayıp' : 'Hasar'} Tazminatı: ${damagePenalty.toFixed(0)} TL)`
                                  : ''}
                              </span>
                              <span className="text-[11px] opacity-90">
                                {item.is_penalty_paid
                                  ? 'Bu ceza / tazminat ödenmiş ve görevli tarafından onaylanmıştır.'
                                  : item.penalty_payment_status === 'PENDING_APPROVAL'
                                  ? 'Ödemeniz iletildi; yönetici ödemeyi aldığını onaylayana kadar yeni kitap ödünç alamaz ve rezerve edemezsiniz.'
                                  : 'Yeni ödünç/rezervasyon yapabilmek için bu borcu ödemelisiniz.'}
                              </span>
                            </div>
                            <span
                              className={`px-2.5 py-1 rounded-full text-[11px] font-bold shrink-0 ${
                                item.is_penalty_paid
                                  ? 'bg-emerald-200 text-emerald-900'
                                  : item.penalty_payment_status === 'PENDING_APPROVAL'
                                  ? 'bg-purple-200 text-purple-900 border border-purple-300 animate-pulse'
                                  : 'bg-rose-100 text-rose-800 border border-rose-300'
                              }`}
                            >
                              {item.is_penalty_paid
                                ? 'Ödendi (Onaylandı)'
                                : item.penalty_payment_status === 'PENDING_APPROVAL'
                                ? 'Ödeme Onayı Bekliyor'
                                : 'Ödenmedi'}
                            </span>
                          </div>
                        )}
                      </div>

                      {(!isReturned || hasUnpaidPenalty) && (
                        <div className="pt-2 flex flex-wrap justify-end gap-2">
                          {isPendingBorrow && (
                            <button
                              onClick={() => handleCancelBorrowRequest(item.id)}
                              disabled={cancellingBorrowId === item.id}
                              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-bold transition-all cursor-pointer disabled:opacity-60"
                            >
                              <Trash2 className="w-4 h-4" />
                              {cancellingBorrowId === item.id ? 'İptal Ediliyor...' : 'Ödünç Talebini İptal Et'}
                            </button>
                          )}

                          {!isReturned && !isPendingBorrow && !isPendingReturn && (
                            <button
                              onClick={() => openReturnModal(item)}
                              disabled={returningId === item.id}
                              className={`w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-white text-xs font-semibold shadow-xs transition-all cursor-pointer disabled:opacity-60 ${
                                isOverdue
                                   ? 'bg-rose-600 hover:bg-rose-700'
                                   : 'bg-indigo-600 hover:bg-indigo-700'
                              }`}
                            >
                              <RotateCcw className="w-4 h-4" />
                              {returningId === item.id
                                ? 'İşleniyor...'
                                : isOverdue
                                ? `İade Talebi & Durum Bildir (${penaltyAmount.toFixed(0)} TL Gecikme)`
                                : 'İade Talebi & Durum Bildir'}
                            </button>
                          )}

                          {hasUnpaidPenalty && (
                            item.penalty_payment_status === 'PENDING_APPROVAL' ? (
                              <button
                                disabled
                                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-purple-100 text-purple-900 border border-purple-300 text-xs font-bold shadow-xs cursor-not-allowed opacity-90"
                              >
                                <Clock className="w-4 h-4 text-purple-700 animate-pulse" />
                                Ödeme Görevli Onayında Bekliyor
                              </button>
                            ) : (
                              <button
                                onClick={() => handlePayPenalty(item.id, penaltyAmount)}
                                disabled={payingPenaltyId === item.id}
                                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-700 disabled:opacity-60 text-white text-xs font-bold shadow-xs transition-all cursor-pointer"
                              >
                                <Banknote className="w-4 h-4" />
                                {payingPenaltyId === item.id
                                  ? 'Ödeniyor...'
                                  : `Borcu Öde (${penaltyAmount.toFixed(2)} TL)`}
                              </button>
                            )
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Pagination Controls */}
              {totalBorrowingPages > 1 && (
                <div className="bg-white rounded-2xl p-3.5 border border-slate-200 flex items-center justify-between gap-2">
                  <button
                    onClick={() => setBorrowingPage((p) => Math.max(1, p - 1))}
                    disabled={safeBorrowingPage <= 1}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-slate-100 hover:bg-slate-200 disabled:opacity-40 text-slate-700 transition-colors cursor-pointer"
                  >
                    <ChevronLeft className="w-4 h-4" />
                    Önceki Sayfa
                  </button>
                  <div className="flex items-center gap-1.5">
                    {Array.from({ length: totalBorrowingPages }, (_, i) => i + 1).map((pageNum) => (
                      <button
                        key={pageNum}
                        onClick={() => setBorrowingPage(pageNum)}
                        className={`w-8 h-8 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                          pageNum === safeBorrowingPage
                            ? 'bg-indigo-600 text-white shadow-xs'
                            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                        }`}
                      >
                        {pageNum}
                      </button>
                    ))}
                  </div>
                  <button
                    onClick={() => setBorrowingPage((p) => Math.min(totalBorrowingPages, p + 1))}
                    disabled={safeBorrowingPage >= totalBorrowingPages}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-slate-100 hover:bg-slate-200 disabled:opacity-40 text-slate-700 transition-colors cursor-pointer"
                  >
                    Sonraki Sayfa
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      ) : reservations.length === 0 ? (
        <div className="bg-white rounded-2xl p-10 text-center border border-dashed border-slate-300">
          <Clock className="w-10 h-10 text-slate-300 mx-auto mb-2" />
          <h3 className="text-base font-bold text-slate-800">Aktif rezervasyonunuz bulunmuyor</h3>
          <p className="text-xs text-slate-500 mt-1">
            Stokta olmayan veya başkasına rezerve edilmiş kitapları detay ekranından rezerve ederek sıraya girebilirsiniz.
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-2xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3.5 px-4">Kitap & ISBN</th>
                  <th className="py-3.5 px-4">Rezervasyon Tarihi</th>
                  <th className="py-3.5 px-4">Rezerve Sırası & Bilgi</th>
                  <th className="py-3.5 px-4">Kalan Süre (24 Saat Zaman Aşımı)</th>
                  <th className="py-3.5 px-4 text-right">İşlem</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {reservations.map((res) => {
                  const book = bookMap[res.book_id];
                  const countdown = formatRemainingCountdown(res.expires_at, nowMs);
                  const turnCountdown = formatRemainingCountdown(res.turn_starts_at, nowMs);
                  const queuePos = res.queue_position || 1;
                  const canBorrow = Boolean(res.can_borrow_now);

                  return (
                    <tr key={res.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-4 px-4">
                        <button
                          onClick={() => book && onSelectBook(book)}
                          className="font-bold text-slate-900 hover:text-indigo-600 text-left cursor-pointer block"
                        >
                          {book ? book.title : `Kitap #${res.book_id.slice(0, 8)}`}
                        </button>
                        <span className="text-xs font-mono text-slate-400">
                          ISBN: {book ? book.isbn : '-'}
                        </span>
                      </td>

                      <td className="py-4 px-4 text-xs text-slate-600 whitespace-nowrap">
                        {new Date(res.reservation_date).toLocaleString('tr-TR')}
                      </td>

                      <td className="py-4 px-4 max-w-md">
                        <div className="flex items-center gap-2 mb-1">
                          <span
                            className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold ${
                              canBorrow
                                ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                                : 'bg-amber-100 text-amber-800 border border-amber-300'
                            }`}
                          >
                            <Users className="w-3.5 h-3.5" />
                            {queuePos}. Sıra {canBorrow ? '(Sıra Sizde!)' : `(Önünüzde ${res.people_ahead || 0} kişi var)`}
                          </span>
                        </div>
                        <p className="text-xs text-slate-600 leading-relaxed">
                          {res.queue_message ||
                            (queuePos > 1
                              ? `Rezerve listesinde ${queuePos}. sıradasınız. Önünüzdeki kullanıcının süresi bittiği anda 24 saatlik süreniz otomatik başlar.`
                              : 'Kitap stoğa girdiği anda (giriş yapmanıza gerek kalmadan) 24 saatlik ödünç alma süreniz otomatik başlar.')}
                        </p>
                      </td>

                      <td className="py-4 px-4 whitespace-nowrap">
                        {countdown ? (
                          <div className="inline-flex flex-col gap-1 px-3 py-1.5 rounded-xl bg-indigo-50 border border-indigo-200 text-indigo-900">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-600 flex items-center gap-1">
                              <Clock className="w-3 h-3 animate-pulse" />
                              Aktif Ödünç Alma Süresi (24 Saat)
                            </span>
                            <span className="text-xs font-mono font-bold">
                              {countdown.text} kaldı
                            </span>
                          </div>
                        ) : turnCountdown ? (
                          <div className="inline-flex flex-col gap-1 px-3 py-1.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-900">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-amber-700 flex items-center gap-1">
                              <Clock className="w-3 h-3 animate-pulse" />
                              Sıranın Size Gelmesine Kalan Maks. Süre
                            </span>
                            <span className="text-xs font-mono font-bold">
                              {turnCountdown.text} sonra 24s sayacınız başlar
                            </span>
                          </div>
                        ) : (
                          <div className="inline-flex flex-col gap-0.5 px-3 py-1.5 rounded-xl bg-slate-100 border border-slate-200 text-slate-700">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1">
                              <Clock className="w-3 h-3 text-slate-400" />
                              Kitap Ödünçte (Stok = 0)
                            </span>
                            <span className="text-[11px] font-medium text-slate-600">
                              Stoğa girdiği anda 24s sayacınız otomatik başlar
                            </span>
                          </div>
                        )}
                      </td>

                      <td className="py-4 px-4 text-right whitespace-nowrap">
                        <div className="inline-flex items-center gap-2">
                          {canBorrow && (
                            <button
                              onClick={() => handleBorrowReservedBook(res)}
                              disabled={borrowingResId === res.id}
                              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white text-xs font-semibold shadow-2xs transition-colors cursor-pointer"
                            >
                              <BookOpen className="w-3.5 h-3.5" />
                              {borrowingResId === res.id ? 'Alınıyor...' : 'Hemen Ödünç Al'}
                            </button>
                          )}
                          <button
                            onClick={() => handleCancelReservation(res.id)}
                            disabled={cancellingResId === res.id}
                            title="Rezervasyonu İptal Et ve Listeden Sil"
                            className="inline-flex items-center gap-1 px-3 py-2 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-semibold transition-colors cursor-pointer"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                            {cancellingResId === res.id ? 'Siliniyor...' : 'İptal Et'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* İade & Fiziksel Durum Kontrol Modalı */}
      {returnModalItem && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden">
            <div className="p-5 sm:p-6 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-indigo-100 text-indigo-700 flex items-center justify-center">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-extrabold text-slate-900">
                    Kitap İade Talebi & Fiziksel Durum Bildirimi
                  </h3>
                  <p className="text-xs text-slate-500">
                    {bookMap[returnModalItem.book_id]?.title || returnModalItem.book_title || 'Kitap İadesi'}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setReturnModalItem(null)}
                className="p-2 rounded-xl hover:bg-slate-200/70 text-slate-500 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleConfirmReturnSubmit} className="p-5 sm:p-6 space-y-4">
              <div className="bg-indigo-50/80 border border-indigo-200 rounded-2xl p-3.5 text-xs text-indigo-900 leading-relaxed">
                <strong className="block mb-1">Kontrollü İade İş Akışı:</strong>
                İade talebiniz kütüphane görevlisinin onay kuyruğuna iletilir. Görevli kitabın fiziksel durumunu kontrol edip onayladığında kitap rafa (+1 stok) geri döner veya hasar/kayıp raporu işlenir.
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-2">
                  Kitabın Fiziksel Durumu Nedir?
                </label>
                <div className="grid grid-cols-1 gap-2.5">
                  <label
                    className={`flex items-start gap-3 p-3.5 rounded-2xl border cursor-pointer transition-all ${
                      returnCondition === 'GOOD'
                        ? 'bg-emerald-50/90 border-emerald-400 ring-1 ring-emerald-200'
                        : 'bg-white border-slate-200 hover:bg-slate-50'
                    }`}
                  >
                    <input
                      type="radio"
                      name="returnCondition"
                      value="GOOD"
                      checked={returnCondition === 'GOOD'}
                      onChange={() => setReturnCondition('GOOD')}
                      className="mt-1"
                    />
                    <div className="text-xs">
                      <span className="font-bold text-slate-900 block">
                        Sağlam / Eksiksiz (Ek Tazminat Yok)
                      </span>
                      <span className="text-slate-500">
                        Kitapta herhangi bir yırtılma, su teması veya sayfa eksikliği bulunmuyor.
                      </span>
                    </div>
                  </label>

                  <label
                    className={`flex items-start gap-3 p-3.5 rounded-2xl border cursor-pointer transition-all ${
                      returnCondition === 'DAMAGED'
                        ? 'bg-amber-50/90 border-amber-400 ring-1 ring-amber-200'
                        : 'bg-white border-slate-200 hover:bg-slate-50'
                    }`}
                  >
                    <input
                      type="radio"
                      name="returnCondition"
                      value="DAMAGED"
                      checked={returnCondition === 'DAMAGED'}
                      onChange={() => setReturnCondition('DAMAGED')}
                      className="mt-1"
                    />
                    <div className="text-xs">
                      <span className="font-bold text-amber-950 block">
                        Hasar Görmüş (+100 TL Hasar Tazminatı)
                      </span>
                      <span className="text-amber-800">
                        Cilt, kapak veya sayfalarda fiziksel hasar oluştu. Görevli incelemesi sonrası hasar raporu oluşturulur.
                      </span>
                    </div>
                  </label>

                  <label
                    className={`flex items-start gap-3 p-3.5 rounded-2xl border cursor-pointer transition-all ${
                      returnCondition === 'LOST'
                        ? 'bg-rose-50/90 border-rose-400 ring-1 ring-rose-200'
                        : 'bg-white border-slate-200 hover:bg-slate-50'
                    }`}
                  >
                    <input
                      type="radio"
                      name="returnCondition"
                      value="LOST"
                      checked={returnCondition === 'LOST'}
                      onChange={() => setReturnCondition('LOST')}
                      className="mt-1"
                    />
                    <div className="text-xs">
                      <span className="font-bold text-rose-950 block">
                        Kayıp Kitap Bildirimi (+250 TL Kayıp Tazminatı)
                      </span>
                      <span className="text-rose-800">
                        Kitap kaybedildi ve teslim edilemiyor. Kitap stoktan kalıcı düşülür ve kayıp tazminatı yansıtılır.
                      </span>
                    </div>
                  </label>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1.5">
                  Açıklama / Görevliye Notunuz (İsteğe Bağlı)
                </label>
                <textarea
                  rows={2}
                  value={returnNotes}
                  onChange={(e) => setReturnNotes(e.target.value)}
                  placeholder={
                    returnCondition === 'GOOD'
                      ? 'Örn: Kitabı danışmaya teslim ettim...'
                      : 'Örn: Arka kapakta hafif yıpranma var / Kitabı otobüste kaybettim...'
                  }
                  className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setReturnModalItem(null)}
                  className="px-4 py-2.5 rounded-xl text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-700 cursor-pointer"
                >
                  Vazgeç
                </button>
                <button
                  type="submit"
                  disabled={returningId === returnModalItem.id}
                  className="px-5 py-2.5 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white shadow-sm cursor-pointer"
                >
                  {returningId === returnModalItem.id
                    ? 'Gönderiliyor...'
                    : 'İade Talebini Onayla & Gönder'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}


