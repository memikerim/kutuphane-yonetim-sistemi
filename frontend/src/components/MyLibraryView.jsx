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
} from 'lucide-react';
import { api } from '../api';

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

export default function MyLibraryView({ notify, onSelectBook }) {
  const [borrowings, setBorrowings] = useState([]);
  const [reservations, setReservations] = useState([]);
  const [bookMap, setBookMap] = useState({});
  const [loading, setLoading] = useState(true);
  const [returningId, setReturningId] = useState(null);
  const [payingPenaltyId, setPayingPenaltyId] = useState(null);
  const [borrowingResId, setBorrowingResId] = useState(null);
  const [cancellingResId, setCancellingResId] = useState(null);
  const [subTab, setSubTab] = useState('borrowings');
  const [nowMs, setNowMs] = useState(Date.now());

  const fetchAll = async () => {
    setLoading(true);
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
      notify(err.message || 'Bilgileriniz yüklenirken hata oluştu', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
  }, []);

  // Live 1-second ticker for 24-hour reservation countdown
  useEffect(() => {
    const timer = setInterval(() => {
      const current = Date.now();
      setNowMs(current);
      // If any active reservation countdown hits 0, refresh from backend so expired reservation is removed
      const anyJustExpired = reservations.some(
        (r) => r.expires_at && new Date(r.expires_at).getTime() <= current
      );
      if (anyJustExpired) {
        fetchAll();
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [reservations]);

  const handleReturnBook = async (borrowingId) => {
    setReturningId(borrowingId);
    try {
      const res = await api.returnBook(borrowingId);
      if (res?.penalty_amount > 0 && !res?.is_penalty_paid) {
        notify(
          `Kitap gecikmeli olarak iade edildi! ${res.penalty_amount} TL gecikme cezası oluştu.`,
          'error'
        );
      } else {
        notify('Kitap başarıyla iade edildi ve stok 1 artırıldı!', 'success');
      }
      await fetchAll();
    } catch (err) {
      notify(err.message || 'İade işlemi başarısız', 'error');
    } finally {
      setReturningId(null);
    }
  };

  const handlePayPenalty = async (borrowingId, amount) => {
    setPayingPenaltyId(borrowingId);
    try {
      await api.payPenalty(borrowingId);
      notify(`${amount} TL gecikme cezanız başarıyla ödendi!`, 'success');
      await fetchAll();
    } catch (err) {
      notify(err.message || 'Ceza ödeme işlemi başarısız', 'error');
    } finally {
      setPayingPenaltyId(null);
    }
  };


  const handleBorrowReservedBook = async (res) => {
    setBorrowingResId(res.id);
    try {
      const d = new Date();
      d.setDate(d.getDate() + 14);
      const dueDateStr = d.toISOString().split('T')[0];

      await api.borrowBook({
        book_id: res.book_id,
        due_date: dueDateStr,
      });
      const bookTitle = bookMap[res.book_id]?.title || 'Kitap';
      notify(
        `"${bookTitle}" başarıyla ödünç alındı ve rezerve listesinden kaldırıldı!`,
        'success'
      );
      await fetchAll();
    } catch (err) {
      notify(err.message || 'Ödünç alma işlemi başarısız', 'error');
    } finally {
      setBorrowingResId(null);
    }
  };

  const handleCancelReservation = async (resId) => {
    setCancellingResId(resId);
    try {
      await api.cancelReservation(resId);
      notify('Rezervasyonunuz iptal edildi ve listeden kaldırıldı.', 'info');
      await fetchAll();
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

  const overdueActiveCount = borrowings.filter(
    (b) => b.status !== 'RETURNED' && (b.status === 'OVERDUE' || (b.overdue_days || 0) > 0)
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
        borrowings.length === 0 ? (
          <div className="bg-white rounded-2xl p-10 text-center border border-dashed border-slate-300">
            <BookOpen className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <h3 className="text-base font-bold text-slate-800">Henüz ödünç aldığınız bir kitap yok</h3>
            <p className="text-xs text-slate-500 mt-1">
              Katalog vitrininden istediğiniz kitabı seçip hemen ödünç alabilirsiniz.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {borrowings.map((item) => {
              const book = bookMap[item.book_id];
              const isReturned = item.status === 'RETURNED';
              const overdueDays = Number(item.overdue_days || 0);
              const penaltyAmount = Number(item.penalty_amount || 0);
              const isOverdue =
                !isReturned &&
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
                          {book ? book.title : `Kitap ID: ${item.book_id.slice(0, 8)}...`}
                        </button>
                        {book && (
                          <p className="text-xs text-slate-500 mt-0.5">
                            ISBN: {book.isbn}
                            {book.authors?.length > 0 &&
                              ` • ${book.authors.map((a) => `${a.first_name} ${a.last_name}`).join(', ')}`}
                          </p>
                        )}
                      </div>

                      {isReturned ? (
                        <span className="shrink-0 inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-slate-100 text-slate-700 border border-slate-300">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                          İade Edildi
                        </span>
                      ) : isOverdue ? (
                        <span className="shrink-0 inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-extrabold bg-rose-600 text-white shadow-xs">
                          <AlertCircle className="w-3.5 h-3.5" />
                          GECİKMİŞ ({overdueDays} Gün)
                        </span>
                      ) : (
                        <span className="shrink-0 inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                          <Clock className="w-3.5 h-3.5" />
                          Aktif Ödünç
                        </span>
                      )}
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-2 border-t border-slate-100 text-xs">
                      <div className="bg-slate-50 p-2.5 rounded-xl">
                        <span className="text-slate-400 block text-[11px]">Ödünç Tarihi</span>
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
                          <span className="text-emerald-600 block text-[11px]">İade Tarihi</span>
                          <span className="font-semibold text-emerald-800 flex items-center gap-1 mt-0.5">
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                            {item.return_date}
                          </span>
                        </div>
                      )}
                    </div>

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
                            : 'bg-amber-50 border-amber-300 text-amber-950'
                        }`}
                      >
                        <div>
                          <span className="font-bold block">
                            Gecikme Cezası: {penaltyAmount.toFixed(2)} TL ({overdueDays} Gün Gecikme)
                          </span>
                          <span className="text-[11px] opacity-80">
                            {item.is_penalty_paid
                              ? 'Bu gecikme cezası ödenmiştir.'
                              : 'Yeni ödünç/rezervasyon yapabilmek için bu cezayı ödemelisiniz.'}
                          </span>
                        </div>
                        <span
                          className={`px-2.5 py-1 rounded-full text-[11px] font-bold shrink-0 ${
                            item.is_penalty_paid
                              ? 'bg-emerald-200 text-emerald-900'
                              : 'bg-rose-100 text-rose-800 border border-rose-300'
                          }`}
                        >
                          {item.is_penalty_paid ? 'Ödendi' : 'Ödenmedi'}
                        </span>
                      </div>
                    )}
                  </div>

                  {(!isReturned || hasUnpaidPenalty) && (
                    <div className="pt-2 flex flex-wrap justify-end gap-2">
                      {!isReturned && (
                        <button
                          onClick={() => handleReturnBook(item.id)}
                          disabled={returningId === item.id}
                          className={`w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-white text-xs font-semibold shadow-xs transition-all cursor-pointer disabled:opacity-60 ${
                            isOverdue
                              ? 'bg-rose-600 hover:bg-rose-700'
                              : 'bg-indigo-600 hover:bg-indigo-700'
                          }`}
                        >
                          <RotateCcw className="w-4 h-4" />
                          {returningId === item.id
                            ? 'İade Ediliyor...'
                            : isOverdue
                            ? `Gecikmeli İade Et (${penaltyAmount.toFixed(0)} TL Ceza)`
                            : 'Kitabı İade Et'}
                        </button>
                      )}

                      {hasUnpaidPenalty && (
                        <button
                          onClick={() => handlePayPenalty(item.id, penaltyAmount)}
                          disabled={payingPenaltyId === item.id}
                          className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-700 disabled:opacity-60 text-white text-xs font-bold shadow-xs transition-all cursor-pointer"
                        >
                          <Banknote className="w-4 h-4" />
                          {payingPenaltyId === item.id
                            ? 'Ödeniyor...'
                            : `Cezayı Öde (${penaltyAmount.toFixed(2)} TL)`}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )
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
                              ? `Rezerve listesinde ${queuePos}. sıradasınız. Diğer kullanıcılar süreleri bitene kadar ödünç almazlarsa ödünç alabilirsiniz.`
                              : 'Kitabı rezerve ettiğinizde ve stok olduğunda kitabı ödünç almak için 24 saatlik süreniz başlar.')}
                        </p>
                      </td>

                      <td className="py-4 px-4 whitespace-nowrap">
                        {countdown ? (
                          <div className="inline-flex flex-col gap-1 px-3 py-1.5 rounded-xl bg-indigo-50 border border-indigo-200 text-indigo-900">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-600 flex items-center gap-1">
                              <Clock className="w-3 h-3 animate-pulse" />
                              Aktif Süre (24 Saat)
                            </span>
                            <span className="text-xs font-mono font-bold">
                              {countdown.text} kaldı
                            </span>
                          </div>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-100 text-slate-600 text-xs font-medium">
                            <Clock className="w-3.5 h-3.5 text-slate-400" />
                            Stok / Sıra Bekleniyor (24s henüz başlamadı)
                          </span>
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
    </div>
  );
}


