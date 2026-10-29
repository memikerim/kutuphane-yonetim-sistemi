import React, { useState, useEffect } from 'react';
import {
  X,
  BookOpen,
  Calendar,
  Building2,
  Users,
  Tag,
  Star,
  BookmarkPlus,
  Clock,
  Send,
  CheckCircle2,
  AlertTriangle,
  Hash,
  Trash2,
  ShieldAlert,
  User,
  ThumbsUp,
  ThumbsDown,
} from 'lucide-react';
import { api } from '../api';

export default function BookDetailModal({
  book: initialBook,
  user,
  onClose,
  onOpenAuth,
  onBookUpdated,
  notify,
}) {
  const [book, setBook] = useState(initialBook);
  const [reviews, setReviews] = useState([]);
  const [loadingReviews, setLoadingReviews] = useState(true);
  const [hasBorrowedBook, setHasBorrowedBook] = useState(false);

  // Default due_date = today + 14 days
  const getDefaultDueDate = () => {
    const d = new Date();
    d.setDate(d.getDate() + 14);
    return d.toISOString().split('T')[0];
  };
  const todayStr = new Date().toISOString().split('T')[0];

  const [dueDate, setDueDate] = useState(getDefaultDueDate());
  const [actionLoading, setActionLoading] = useState(false);
  const [nowMs, setNowMs] = useState(Date.now());

  // Onay ve İş Akışı Kontrol State'leri
  const [confirmMode, setConfirmMode] = useState(null); // null | 'borrow' | 'reserve'
  const [borrowNotes, setBorrowNotes] = useState('');
  const [rulesAccepted, setRulesAccepted] = useState(true);

  // Kitap Bazlı Okuma ve Stok Geçmişi State'leri
  const [detailTab, setDetailTab] = useState('reviews'); // 'reviews' | 'reading_history' | 'stock_history'
  const [bookHistory, setBookHistory] = useState(null);

  // Review form state
  const [rating, setRating] = useState(5);
  const [hoverRating, setHoverRating] = useState(0);
  const [comment, setComment] = useState('');
  const [submittingReview, setSubmittingReview] = useState(false);
  const [reviewError, setReviewError] = useState(null);
  const [deletingReviewId, setDeletingReviewId] = useState(null);
  const [reactingReviewId, setReactingReviewId] = useState(null);

  const isAdmin = Boolean(user?.roles?.includes('ADMIN'));

  const loadBookAndReviews = async () => {
    setLoadingReviews(true);
    try {
      const promises = [
        api.getBook(initialBook.id),
        api.getReviews(initialBook.id),
        api.getBookHistory(initialBook.id).catch(() => null),
      ];
      if (user) {
        promises.push(api.getMyBorrowings().catch(() => []));
      }
      const [freshBook, bookReviews, historyData, myBorrowings] = await Promise.all(promises);
      if (freshBook) setBook(freshBook);
      setReviews(bookReviews || []);
      if (historyData) setBookHistory(historyData);
      if (user && Array.isArray(myBorrowings)) {
        const borrowed = myBorrowings.some(
          (b) => b.book_id === initialBook.id && b.approval_status !== 'REJECTED'
        );
        setHasBorrowedBook(borrowed);
      } else {
        setHasBorrowedBook(false);
      }
      return freshBook;
    } catch (err) {
      notify(err.message || 'Kitap detayları yüklenemedi', 'error');
      return null;
    } finally {
      setLoadingReviews(false);
    }
  };

  useEffect(() => {
    loadBookAndReviews();
  }, [initialBook.id, user?.id]);

  useEffect(() => {
    const timer = setInterval(() => {
      const current = Date.now();
      setNowMs(current);
      if (
        book.active_reservation_expires_at &&
        new Date(book.active_reservation_expires_at).getTime() <= current
      ) {
        loadBookAndReviews().then((fresh) => {
          if (onBookUpdated) onBookUpdated(fresh);
        });
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [book.active_reservation_expires_at]);

  const initiateBorrow = () => {
    if (!user) {
      notify('Kitap ödünç almak için lütfen giriş yapın.', 'info');
      onClose();
      onOpenAuth('login');
      return;
    }
    if (user.is_banned) {
      notify(
        `Hesabınız yönetici tarafından kısıtlanmıştır: ${
          user.ban_reason || 'Yeni kitap ödünç alamazsınız.'
        }`,
        'error'
      );
      return;
    }
    if ((user.pending_penalty_approval_count || 0) > 0) {
      notify(
        'Ödemiş olduğunuz gecikme veya kayıp/hasar tazminat bedelinin yönetici tarafından onaylanması beklenmektedir. Yönetici onaylayana kadar yeni kitap ödünç alamazsınız.',
        'error'
      );
      return;
    }
    if ((user.overdue_books_count || 0) > 0 || (user.unpaid_penalty_total || 0) > 0) {
      notify(
        'Gecikmiş kitabınızı iade edene ve gecikme veya kayıp/hasar tazminat borçlarınızı ödeyene kadar yeni kitap ödünç alamazsınız.',
        'error'
      );
      return;
    }
    setRulesAccepted(true);
    setConfirmMode('borrow');
  };

  const initiateReserve = () => {
    if (!user) {
      notify('Rezervasyon yapmak için lütfen giriş yapın.', 'info');
      onClose();
      onOpenAuth('login');
      return;
    }
    if (user.is_banned) {
      notify(
        `Hesabınız yönetici tarafından kısıtlanmıştır: ${
          user.ban_reason || 'Yeni rezervasyon yapamazsınız.'
        }`,
        'error'
      );
      return;
    }
    if ((user.pending_penalty_approval_count || 0) > 0) {
      notify(
        'Ödemiş olduğunuz gecikme veya kayıp/hasar tazminat bedelinin yönetici tarafından onaylanması beklenmektedir. Yönetici onaylayana kadar yeni rezervasyon yapamazsınız.',
        'error'
      );
      return;
    }
    if ((user.overdue_books_count || 0) > 0 || (user.unpaid_penalty_total || 0) > 0) {
      notify(
        'Gecikmiş kitabınızı iade edene ve gecikme veya kayıp/hasar tazminat borçlarınızı ödeyene kadar yeni rezervasyon yapamazsınız.',
        'error'
      );
      return;
    }
    setRulesAccepted(true);
    setConfirmMode('reserve');
  };

  const handleBorrow = async () => {
    if (!user) {
      notify('Kitap ödünç almak için lütfen giriş yapın.', 'info');
      onClose();
      onOpenAuth('login');
      return;
    }
    if (!rulesAccepted) {
      notify('Lütfen kütüphane ödünç alma ve sorumluluk kurallarını onaylayın.', 'error');
      return;
    }

    setActionLoading(true);
    try {
      await api.borrowBook({
        book_id: book.id,
        due_date: dueDate,
        request_approval: true,
        notes: borrowNotes.trim() || undefined,
      });
      notify(
        `"${book.title}" için ödünç talebiniz görevli onayına iletildi. Talebiniz reddedilebileceğinden Bildirimler sekmesinden onay bildirimini görmeden lütfen kütüphaneye gelmeyiniz.`,
        'success'
      );
      setConfirmMode(null);
      setBorrowNotes('');
      const fresh = await loadBookAndReviews();
      if (onBookUpdated) onBookUpdated(fresh);
    } catch (err) {
      notify(err.message || 'Ödünç alma işlemi başarısız', 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReserve = async () => {
    if (!user) {
      notify('Rezervasyon yapmak için lütfen giriş yapın.', 'info');
      onClose();
      onOpenAuth('login');
      return;
    }
    if (!rulesAccepted) {
      notify('Lütfen rezervasyon kurallarını onaylayın.', 'error');
      return;
    }

    setActionLoading(true);
    try {
      const res = await api.createReservation({
        book_id: book.id,
      });
      notify(
        res?.queue_message || `"${book.title}" için rezervasyon sırasına girdiniz.`,
        'success'
      );
      setConfirmMode(null);
      const fresh = await loadBookAndReviews();
      if (onBookUpdated) onBookUpdated(fresh);
    } catch (err) {
      notify(err.message || 'Rezervasyon oluşturulamadı', 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReviewSubmit = async (e) => {
    e.preventDefault();
    setReviewError(null);

    if (!user) {
      notify('Değerlendirme yapmak için lütfen giriş yapın.', 'info');
      onClose();
      onOpenAuth('login');
      return;
    }

    setSubmittingReview(true);
    try {
      await api.createReview({
        book_id: book.id,
        rating: Number(rating),
        comment: comment.trim() || null,
      });
      notify('Değerlendirmeniz başarıyla kaydedildi!', 'success');
      setComment('');
      setRating(5);
      setReviewError(null);
      const updatedReviews = await api.getReviews(book.id);
      setReviews(updatedReviews || []);
    } catch (err) {
      const msg = err.message || 'Yorumunuz eklenemedi.';
      setReviewError(msg);
      notify(msg, 'error');
    } finally {
      setSubmittingReview(false);
    }
  };

  const handleDeleteReview = async (reviewId) => {
    setDeletingReviewId(reviewId);
    setReviewError(null);
    try {
      await api.deleteReview(reviewId);
      notify('Yorum başarıyla silindi.', 'success');
      const updatedReviews = await api.getReviews(book.id);
      setReviews(updatedReviews || []);
    } catch (err) {
      notify(err.message || 'Yorum silinemedi.', 'error');
    } finally {
      setDeletingReviewId(null);
    }
  };

  const handleReactReview = async (reviewId, value) => {
    if (!user) {
      notify('Yorumları beğenmek veya beğenmemek için lütfen giriş yapın.', 'info');
      onClose();
      onOpenAuth('login');
      return;
    }

    setReactingReviewId(reviewId);
    try {
      const updatedReview = await api.reactToReview(reviewId, value);
      setReviews((prev) =>
        prev.map((r) => (r.id === reviewId ? updatedReview : r))
      );
    } catch (err) {
      notify(err.message || 'Tepki kaydedilemedi.', 'error');
    } finally {
      setReactingReviewId(null);
    }
  };

  const averageRating =
    reviews.length > 0
      ? (reviews.reduce((acc, r) => acc + r.rating, 0) / reviews.length).toFixed(1)
      : null;

  const reservedCount = book.reserved_count || 0;
  const queueIds = book.reservation_queue_user_ids || [];
  const userQueueIdx = user ? queueIds.indexOf(user.id) : -1;
  const userQueuePos = userQueueIdx >= 0 ? userQueueIdx + 1 : null;
  const userHasActiveSlot =
    book.stock_count > 0 && userQueuePos !== null && userQueuePos <= book.stock_count;
  const allStockReservedByOthers =
    book.stock_count > 0 && reservedCount >= book.stock_count && !userHasActiveSlot;

  const activeSlotCountdownText = (() => {
    if (!book.active_reservation_expires_at) return null;
    const targetMs = new Date(book.active_reservation_expires_at).getTime();
    const diffSec = Math.max(0, Math.floor((targetMs - nowMs) / 1000));
    const hours = Math.floor(diffSec / 3600);
    const minutes = Math.floor((diffSec % 3600) / 60);
    const seconds = diffSec % 60;
    return `${hours} saat ${String(minutes).padStart(2, '0')} dk ${String(seconds).padStart(2, '0')} sn`;
  })();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-slate-900/60 backdrop-blur-xs overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden my-auto">
        {/* Top Modal Header */}
        <div className="px-5 sm:px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-indigo-100 text-indigo-700 flex items-center justify-center shrink-0">
              <BookOpen className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <h2 className="text-base sm:text-lg font-bold text-slate-900 truncate">
                {book.title}
              </h2>
              <p className="text-xs text-slate-500">Kitap Detayı, Ödünç & Değerlendirmeler</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="p-5 sm:p-6 overflow-y-auto space-y-6">
          {/* Book Metadata Card */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 bg-slate-50/70 p-4 sm:p-5 rounded-2xl border border-slate-200/80">
            {/* Left Cover Visual (Kitap Kapağı Tam Sığdırma) */}
            <div className="relative rounded-2xl overflow-hidden bg-gradient-to-b from-slate-100 to-slate-200/80 border border-slate-200/90 shadow-md min-h-[240px] max-h-[360px] p-4 flex items-center justify-center text-center group">
              {book.cover_url ? (
                <>
                  <img
                    src={book.cover_url}
                    alt=""
                    aria-hidden="true"
                    className="absolute inset-0 w-full h-full object-cover blur-2xl opacity-25 scale-125 pointer-events-none"
                  />
                  <img
                    src={book.cover_url}
                    alt={book.title}
                    className="relative z-0 max-h-[320px] max-w-full object-contain rounded-xl shadow-lg group-hover:scale-105 transition-transform duration-300"
                    onError={(e) => {
                      e.currentTarget.style.display = 'none';
                      if (e.currentTarget.nextElementSibling) {
                        e.currentTarget.nextElementSibling.classList.remove('hidden');
                        e.currentTarget.nextElementSibling.classList.add('flex');
                      }
                    }}
                  />
                  <div className="hidden flex-col items-center justify-center p-6 w-full h-full min-h-[220px] bg-gradient-to-br from-indigo-600 via-indigo-700 to-violet-800 text-white rounded-xl">
                    <BookOpen className="w-14 h-14 mb-3 opacity-90" />
                    <h3 className="font-bold text-sm line-clamp-2">{book.title}</h3>
                    <span className="mt-2 px-2.5 py-0.5 rounded-full text-[11px] bg-white/20 backdrop-blur-xs font-medium">
                      {book.published_year || 'Yıl Belirtilmemiş'}
                    </span>
                  </div>
                </>
              ) : (
                <div className="flex flex-col items-center justify-center p-6 w-full h-full min-h-[220px] bg-gradient-to-br from-indigo-600 via-indigo-700 to-violet-800 text-white rounded-xl shadow-inner">
                  <BookOpen className="w-14 h-14 mb-3 opacity-90" />
                  <h3 className="font-bold text-sm line-clamp-2">{book.title}</h3>
                  <span className="mt-2 px-2.5 py-0.5 rounded-full text-[11px] bg-white/20 backdrop-blur-xs font-medium">
                    {book.published_year || 'Yıl Belirtilmemiş'}
                  </span>
                </div>
              )}

              {averageRating && (
                <div className="absolute bottom-3 left-1/2 -translate-x-1/2 inline-flex items-center gap-1 px-3 py-1 rounded-xl bg-slate-900/85 backdrop-blur-md border border-white/20 text-amber-300 text-xs font-bold shadow-lg z-10">
                  <Star className="w-3.5 h-3.5 fill-amber-300 text-amber-300" />
                  <span>{averageRating} / 5.0</span>
                  <span className="text-[10px] text-slate-300">({reviews.length})</span>
                </div>
              )}
            </div>

            {/* Right Metadata Details */}
            <div className="md:col-span-2 flex flex-col justify-between space-y-4">
              <div className="space-y-3">
                {/* Stock & Reservation Badges */}
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-1.5">
                    {book.stock_count > 0 ? (
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Stokta Mevcut ({book.stock_count} Adet)
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        Stok Tükendi (0 Adet)
                      </span>
                    )}

                    {userHasActiveSlot ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-indigo-100 text-indigo-800 border border-indigo-300">
                        <Clock className="w-3.5 h-3.5" />
                        Sizin İçin Rezerveli (24 Saat)
                      </span>
                    ) : allStockReservedByOthers ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-300">
                        <Clock className="w-3.5 h-3.5" />
                        Başkasına Rezerveli ({reservedCount} Kişi Sırada)
                      </span>
                    ) : reservedCount > 0 ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200">
                        <Clock className="w-3.5 h-3.5" />
                        Rezerve Sırası: {reservedCount} Kişi
                      </span>
                    ) : null}
                  </div>

                  <span className="inline-flex items-center gap-1 text-xs font-mono text-slate-500 bg-white px-2.5 py-1 rounded-lg border border-slate-200">
                    <Hash className="w-3.5 h-3.5 text-slate-400" />
                    ISBN: {book.isbn}
                  </span>
                </div>

                {/* Authors */}
                <div className="flex items-start gap-2 text-sm">
                  <Users className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold text-slate-700">Yazarlar: </span>
                    <span className="text-slate-600">
                      {book.authors?.length > 0
                        ? book.authors.map((a) => `${a.first_name} ${a.last_name}`).join(', ')
                        : 'Belirtilmemiş'}
                    </span>
                  </div>
                </div>

                {/* Publisher */}
                <div className="flex items-start gap-2 text-sm">
                  <Building2 className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold text-slate-700">Yayınevi: </span>
                    <span className="text-slate-600">
                      {book.publisher ? book.publisher.name : 'Belirtilmemiş'}
                    </span>
                  </div>
                </div>

                {/* Categories */}
                <div className="flex items-start gap-2 text-sm">
                  <Tag className="w-4 h-4 text-indigo-600 shrink-0 mt-1" />
                  <div className="flex flex-wrap gap-1.5">
                    {book.categories?.length > 0 ? (
                      book.categories.map((c) => (
                        <span
                          key={c.id}
                          className="px-2.5 py-0.5 rounded-lg text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-200/60"
                        >
                          {c.name}
                        </span>
                      ))
                    ) : (
                      <span className="text-slate-500 text-xs">Kategori atanmamış</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Borrowing & Reservation Action Box */}
              <div className="pt-3 border-t border-slate-200/80 space-y-2.5">
                {user?.is_banned ? (
                  <div className="p-3 rounded-xl bg-rose-50 border border-rose-300 text-rose-900 text-xs flex items-start gap-2">
                    <ShieldAlert className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-bold">Hesabınız Kısıtlanmıştır (Banlı):</p>
                      <p className="mt-0.5 text-rose-800">
                        {user.ban_reason ||
                          'Kitap iadeniz ve borç ödemeleriniz tamamlanana kadar yeni ödünç alma, rezervasyon ve yorum işlemleri kapalıdır.'}
                      </p>
                    </div>
                  </div>
                ) : (user?.pending_penalty_approval_count || 0) > 0 ? (
                  <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-300 text-amber-950 text-xs flex items-start gap-2">
                    <Clock className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-bold">Ödeme Onayı Bekleniyor:</p>
                      <p className="mt-0.5 text-amber-800">
                        Ödemiş olduğunuz gecikme veya kayıp/hasar tazminat bedelinin yönetici tarafından onaylanması beklenmektedir ({user.pending_penalty_approval_count} işlem). Yönetici ödemeyi aldığını onaylayana kadar yeni kitap ödünç alamaz veya rezervasyon oluşturamazsınız.
                      </p>
                    </div>
                  </div>
                ) : (user?.overdue_books_count || 0) > 0 || (user?.unpaid_penalty_total || 0) > 0 ? (
                  <div className="p-3 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 text-xs flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-bold">Yeni Ödünç / Rezervasyon Kısıtlaması:</p>
                      <p className="mt-0.5 text-amber-800">
                        Hesabınızda{' '}
                        {user.overdue_books_count > 0 && (
                          <strong>{user.overdue_books_count} adet gecikmiş kitap </strong>
                        )}
                        {user.unpaid_penalty_total > 0 && (
                          <strong>
                            {Number(user.unpaid_penalty_total).toFixed(2)} TL ödenmemiş gecikme / kayıp-hasar borcu{' '}
                          </strong>
                        )}
                        bulunmaktadır. Gecikmiş kitabınızı iade edene ve borcunuzu ödeyene kadar yeni kitap ödünç alamazsınız.
                      </p>
                    </div>
                  </div>
                ) : null}

                {userHasActiveSlot ? (
                  <div className="space-y-3">
                    <div className="bg-emerald-50 border border-emerald-200 p-3 rounded-xl text-xs text-emerald-900">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="font-bold flex items-center gap-1.5">
                          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                          Rezerve sırası sizde ({userQueuePos}. sıradasınız)!
                        </p>
                        {activeSlotCountdownText && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg bg-emerald-200/80 text-emerald-950 font-mono font-bold text-[11px]">
                            <Clock className="w-3 h-3 animate-pulse" />
                            Kalan Süre: {activeSlotCountdownText}
                          </span>
                        )}
                      </div>
                      <p className="text-emerald-700 mt-1">
                        Kitap stoğu sizin için ayrıldı; giriş yapmanıza gerek kalmadan başlayan 24 saatlik süreniz dolmadan hemen ödünç alabilirsiniz.
                      </p>
                    </div>
                    <div className="flex flex-col sm:flex-row sm:items-end gap-3">
                      <div className="flex-1">
                        <label className="block text-xs font-semibold text-slate-700 mb-1">
                          Planlanan İade Tarihi (due_date)
                        </label>
                        <div className="relative">
                          <Calendar className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                          <input
                            type="date"
                            min={todayStr}
                            value={dueDate}
                            onChange={(e) => setDueDate(e.target.value)}
                            className="w-full pl-9 pr-3 py-2 rounded-xl border border-slate-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          />
                        </div>
                      </div>
                      <button
                        onClick={initiateBorrow}
                        disabled={actionLoading}
                        className="py-2.5 px-5 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white font-semibold text-sm shadow-sm flex items-center justify-center gap-2 transition-all cursor-pointer"
                      >
                        <BookOpen className="w-4 h-4" />
                        {actionLoading ? 'İşleniyor...' : 'Rezerve Kitabı Ödünç Talep Et'}
                      </button>
                    </div>
                  </div>
                ) : userQueuePos !== null ? (
                  <div className="bg-amber-50/90 border border-amber-200 p-3.5 rounded-xl text-xs text-amber-900 space-y-1.5">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="font-bold flex items-center gap-1.5">
                        <Clock className="w-4 h-4 text-amber-600 shrink-0" />
                        Rezerve listesinde {userQueuePos}. sıradasınız
                        {userQueuePos > 1 ? ` (Önünüzde ${userQueuePos - 1} kişi var)` : ''}
                      </p>
                      {activeSlotCountdownText && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg bg-amber-200/80 text-amber-950 font-mono font-bold text-[11px]">
                          <Clock className="w-3 h-3 animate-pulse" />
                          Öndeki Sıra Bitişi: {activeSlotCountdownText}
                        </span>
                      )}
                    </div>
                    <p className="text-amber-800 leading-relaxed">
                      {userQueuePos > 1
                        ? `Rezerve listesinde ${userQueuePos}. sıradasınız. Önünüzdeki kullanıcının süresi bittiği anda (giriş yapmanıza gerek olmadan) 24 saatlik süreniz otomatik başlar.`
                        : 'Kitap ödünç alınma stoğuna girdiği anda (giriş yapmanıza gerek olmadan) 24 saatlik ödünç alma süreniz otomatik başlar.'}
                    </p>
                  </div>
                ) : allStockReservedByOthers ? (
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 bg-amber-50/80 border border-amber-200 p-3.5 rounded-xl">
                    <div className="text-xs text-amber-900 space-y-1">
                      <p className="font-bold">
                        Stokta {book.stock_count} adet var ancak şu an başkasına rezerve edilmiş durumda!
                      </p>
                      {activeSlotCountdownText && (
                        <p className="font-mono font-bold text-amber-800">
                          Mevcut sıradaki kullanıcının kalan süresi: {activeSlotCountdownText}
                        </p>
                      )}
                      <p className="text-amber-700">
                        Rezerve eden kullanıcıların 24 saatlik süresi bitene kadar başka kullanıcı ödünç alamaz, sadece rezerve ederek sıraya girebilirsiniz (Sırada: {reservedCount} kişi).
                      </p>
                    </div>
                    <button
                      onClick={initiateReserve}
                      disabled={actionLoading}
                      className="w-full sm:w-auto shrink-0 py-2.5 px-4 rounded-xl bg-amber-600 hover:bg-amber-700 disabled:opacity-60 text-white font-semibold text-xs shadow-xs flex items-center justify-center gap-1.5 transition-all cursor-pointer"
                    >
                      <Clock className="w-4 h-4" />
                      {actionLoading
                        ? 'İşleniyor...'
                        : `Rezerve Et (${reservedCount + 1}. Sıraya Gir)`}
                    </button>
                  </div>
                ) : book.stock_count > 0 ? (
                  <div className="space-y-3">
                    <div className="flex flex-col sm:flex-row sm:items-end gap-3">
                      <div className="flex-1">
                        <label className="block text-xs font-semibold text-slate-700 mb-1">
                          Planlanan İade Tarihi (due_date)
                        </label>
                        <div className="relative">
                          <Calendar className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                          <input
                            type="date"
                            min={todayStr}
                            value={dueDate}
                            onChange={(e) => setDueDate(e.target.value)}
                            className="w-full pl-9 pr-3 py-2 rounded-xl border border-slate-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          />
                        </div>
                      </div>
                      <button
                        onClick={initiateBorrow}
                        disabled={actionLoading}
                        className="py-2.5 px-5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white font-semibold text-sm shadow-sm shadow-indigo-200 flex items-center justify-center gap-2 transition-all cursor-pointer"
                      >
                        <BookOpen className="w-4 h-4" />
                        {actionLoading ? 'İşleniyor...' : 'Ödünç Talebi Oluştur'}
                      </button>
                      <button
                        onClick={initiateReserve}
                        disabled={actionLoading}
                        title="Bu kitap için rezervasyon oluştur (24 saat geçerli)"
                        className="py-2.5 px-4 rounded-xl bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 font-semibold text-xs flex items-center justify-center gap-1.5 transition-all cursor-pointer"
                      >
                        <BookmarkPlus className="w-4 h-4 text-indigo-600" />
                        Rezerve Et
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 bg-amber-50/80 border border-amber-200 p-3.5 rounded-xl">
                    <div className="text-xs text-amber-900">
                      <p className="font-bold">Bu kitap şu an stokta bulunmuyor (Stok = 0).</p>
                      <p className="text-amber-700 mt-0.5">
                        {reservedCount > 0
                          ? `Şu an sırada ${reservedCount} kişi bekliyor. Kitabı rezerve ettiğinizde (${reservedCount + 1}. sıra) ve stok olduğunda, sıra size geldiğinde kitabı ödünç almak için 24 saatlik süreniz başlar.`
                          : 'Kitabı rezerve ettiğinizde ve stok olduğunda kitabı ödünç almak için 24 saatlik süreniz başlar.'}
                      </p>
                    </div>
                    <button
                      onClick={initiateReserve}
                      disabled={actionLoading}
                      className="w-full sm:w-auto shrink-0 py-2.5 px-4 rounded-xl bg-amber-600 hover:bg-amber-700 disabled:opacity-60 text-white font-semibold text-xs shadow-xs flex items-center justify-center gap-1.5 transition-all cursor-pointer"
                    >
                      <Clock className="w-4 h-4" />
                      {actionLoading
                        ? 'İşleniyor...'
                        : reservedCount > 0
                        ? `Rezerve Et (${reservedCount + 1}. Sıraya Gir)`
                        : 'Rezerve Et (1. Sıraya Gir)'}
                    </button>
                  </div>
                )}

                {/* İş Akışı Onay & Kontrol Kutusu (Borrow / Reserve Confirmation) */}
                {confirmMode === 'borrow' && (
                  <div className="mt-3 p-4 rounded-2xl bg-indigo-50/90 border-2 border-indigo-300 space-y-3 shadow-sm">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-extrabold uppercase bg-indigo-600 text-white mb-1">
                          ÖDÜNÇ ALMA ONAY VE KONTROL ADIMI
                        </span>
                        <h4 className="text-sm font-bold text-indigo-950">
                          "{book.title}" Ödünç Talebi Özeti
                        </h4>
                      </div>
                      <button
                        type="button"
                        onClick={() => setConfirmMode(null)}
                        className="p-1 text-indigo-500 hover:text-indigo-800 cursor-pointer"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>

                    {/* Önemli Uyarı: Görevli Onayı & Bildirim Uyarısı */}
                    <div className="p-3 rounded-xl bg-amber-50 border-2 border-amber-300 text-amber-950 text-xs space-y-1">
                      <div className="flex items-center gap-1.5 font-extrabold text-amber-900">
                        <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                        <span>Önemli Uyarı: Bildirim Gelmeden Kütüphaneye Gelmeyiniz</span>
                      </div>
                      <p className="text-[11px] leading-relaxed text-amber-900">
                        Ödünç talebiniz kütüphane görevlisinin incelemesine sunulur. Yoğunluk, kitap kondisyonu veya envanter durumu gereği <strong>talebiniz reddedilebilir</strong>.
                      </p>
                      <p className="text-[11px] font-bold text-amber-950">
                        ⚠️ Hesabınızdaki "Bildirimler" sekmesinden onay bildirimini görmeden lütfen kütüphaneye teslim almaya gelmeyiniz!
                      </p>
                    </div>

                    <div className="bg-white/90 rounded-xl p-3 border border-indigo-200 text-xs text-slate-700 space-y-1.5">
                      <p>
                        • <strong>Planlanan Son Teslim Tarihi:</strong>{' '}
                        <span className="font-bold text-indigo-700">{dueDate}</span>
                      </p>
                      <p>
                        • <strong>İş Akışı & Görevli Onayı:</strong> Talebiniz oluşturulduğunda stoktan{' '}
                        <strong>1 adet kopya sizin için ayrılır (-1)</strong> ve görevli (Admin) onay kuyruğuna düşer. Görevli onayladığında kitap aktif teslim statüsüne geçer.
                      </p>
                      <p>
                        • <strong>Ceza & Sorumluluk Kuralları:</strong> Gecikmelerde günlük{' '}
                        <strong>10 TL</strong> gecikme cezası; kitabın hasarlı iadesinde{' '}
                        <strong>100 TL hasar tazminatı</strong>, kaybı halinde ise{' '}
                        <strong>250 TL kayıp bedeli</strong> uygulanır.
                      </p>
                    </div>

                    <div>
                      <label className="block text-[11px] font-bold text-indigo-900 mb-1">
                        Görevliye Notunuz (Opsiyonel)
                      </label>
                      <input
                        type="text"
                        value={borrowNotes}
                        onChange={(e) => setBorrowNotes(e.target.value)}
                        placeholder="Örn: Öğleden sonra kütüphane bankosundan teslim alacağım..."
                        className="w-full px-3 py-2 rounded-xl border border-indigo-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                    </div>

                    <label className="flex items-center gap-2 text-xs font-semibold text-indigo-950 cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={rulesAccepted}
                        onChange={(e) => setRulesAccepted(e.target.checked)}
                        className="rounded border-indigo-300 text-indigo-600 focus:ring-indigo-500"
                      />
                      Kütüphane ödünç kurallarını, teslim tarihini ve hasar/kayıp sorumluluğunu kabul ediyorum.
                    </label>

                    <div className="flex items-center justify-end gap-2 pt-1">
                      <button
                        type="button"
                        onClick={() => setConfirmMode(null)}
                        className="px-3.5 py-2 rounded-xl bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 text-xs font-semibold cursor-pointer"
                      >
                        Vazgeç
                      </button>
                      <button
                        type="button"
                        onClick={handleBorrow}
                        disabled={actionLoading || !rulesAccepted}
                        className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-bold shadow-xs flex items-center gap-1.5 cursor-pointer"
                      >
                        <CheckCircle2 className="w-4 h-4" />
                        {actionLoading ? 'Gönderiliyor...' : 'Onayla ve Ödünç Talebi Gönder'}
                      </button>
                    </div>
                  </div>
                )}

                {confirmMode === 'reserve' && (
                  <div className="mt-3 p-4 rounded-2xl bg-amber-50/95 border-2 border-amber-300 space-y-3 shadow-sm">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-extrabold uppercase bg-amber-600 text-white mb-1">
                          REZERVASYON ONAY ADIMI
                        </span>
                        <h4 className="text-sm font-bold text-amber-950">
                          "{book.title}" Rezervasyon Sırası Onayı
                        </h4>
                      </div>
                      <button
                        type="button"
                        onClick={() => setConfirmMode(null)}
                        className="p-1 text-amber-600 hover:text-amber-900 cursor-pointer"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>

                    <div className="bg-white/90 rounded-xl p-3 border border-amber-200 text-xs text-slate-700 space-y-1.5">
                      <p>
                        • <strong>Tahmini Sıranız:</strong>{' '}
                        <span className="font-bold text-amber-800">{reservedCount + 1}. Sıra</span>
                      </p>
                      <p>
                        • <strong>24 Saat Kuralı:</strong> Kitap stoğa girdiğinde ve sıra size geldiğinde, sisteme giriş yapmanıza gerek kalmadan{' '}
                        <strong>24 saatlik ödünç alma süreniz otomatik başlar</strong>. 24 saat içinde talep oluşturulmazsa sıra bir sonraki üyeye devredilir.
                      </p>
                    </div>

                    <label className="flex items-center gap-2 text-xs font-semibold text-amber-950 cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={rulesAccepted}
                        onChange={(e) => setRulesAccepted(e.target.checked)}
                        className="rounded border-amber-300 text-amber-600 focus:ring-amber-500"
                      />
                      24 saatlik otomatik rezervasyon sırası kurallarını okudum ve onaylıyorum.
                    </label>

                    <div className="flex items-center justify-end gap-2 pt-1">
                      <button
                        type="button"
                        onClick={() => setConfirmMode(null)}
                        className="px-3.5 py-2 rounded-xl bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 text-xs font-semibold cursor-pointer"
                      >
                        Vazgeç
                      </button>
                      <button
                        type="button"
                        onClick={handleReserve}
                        disabled={actionLoading || !rulesAccepted}
                        className="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-xs font-bold shadow-xs flex items-center gap-1.5 cursor-pointer"
                      >
                        <Clock className="w-4 h-4" />
                        {actionLoading ? 'İşleniyor...' : 'Onayla ve Rezervasyon Sırasına Gir'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Alt Sekmeler: Değerlendirmeler | Kitap Bazlı Okuma Geçmişi | Stok & Hasar/Kayıp Raporları */}
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-2.5">
              <div className="flex flex-wrap items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => setDetailTab('reviews')}
                  className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                    detailTab === 'reviews'
                      ? 'bg-indigo-600 text-white shadow-xs'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  <Star className="w-3.5 h-3.5" />
                  Değerlendirmeler ({reviews.length})
                </button>
                <button
                  type="button"
                  onClick={() => setDetailTab('reading_history')}
                  className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                    detailTab === 'reading_history'
                      ? 'bg-indigo-600 text-white shadow-xs'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  <BookOpen className="w-3.5 h-3.5" />
                  Kitap Bazlı Okuma Geçmişi ({bookHistory?.stats?.total_borrow_count || 0})
                </button>
                <button
                  type="button"
                  onClick={() => setDetailTab('stock_history')}
                  className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                    detailTab === 'stock_history'
                      ? 'bg-indigo-600 text-white shadow-xs'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  <ShieldAlert className="w-3.5 h-3.5" />
                  Geçmiş Stok & Hasar/Kayıp ({bookHistory?.stock_movements?.length || 0})
                </button>
              </div>
              {averageRating && detailTab === 'reviews' && (
                <span className="text-xs font-bold text-slate-600 bg-slate-100 px-2.5 py-1 rounded-lg">
                  Ortalama Puan: {averageRating} / 5
                </span>
              )}
            </div>

            {detailTab === 'reviews' && (
              <>
                {/* Add Review Form */}
                <form
                  onSubmit={handleReviewSubmit}
                  className="bg-slate-50 p-4 rounded-2xl border border-slate-200/80 space-y-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-bold text-slate-700">
                      Bu Kitabı Değerlendirin (1 - 5 Yıldız):
                    </span>
                    <div className="flex items-center gap-1">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <button
                          key={star}
                          type="button"
                          onClick={() => setRating(star)}
                          onMouseEnter={() => setHoverRating(star)}
                          onMouseLeave={() => setHoverRating(0)}
                          className="p-1 focus:outline-none transition-transform hover:scale-110"
                        >
                          <Star
                            className={`w-6 h-6 ${
                              star <= (hoverRating || rating)
                                ? 'text-amber-400 fill-amber-400'
                                : 'text-slate-300'
                            }`}
                          />
                        </button>
                      ))}
                      <span className="ml-1.5 text-xs font-bold text-amber-700 bg-amber-100 px-2 py-0.5 rounded-md">
                        {rating} / 5
                      </span>
                    </div>
                  </div>

                  {user?.is_banned && (
                    <div className="flex items-start gap-2 px-3 py-2.5 rounded-xl bg-rose-50 border border-rose-300 text-rose-900 text-xs">
                      <ShieldAlert className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                      <span>
                        <strong>Yorum Yapma Kısıtlaması:</strong>{' '}
                        {user.ban_reason ||
                          'Hesabınız yönetici tarafından kısıtlandığı için yeni değerlendirme ve yorum bırakamazsınız.'}
                      </span>
                    </div>
                  )}

                  {user && !user.is_banned && !hasBorrowedBook && (
                    <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs">
                      <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                      <span>
                        Bu kitaba değerlendirme ve yorum bırakabilmek için kitabı daha önce ödünç almış olmanız gerekmektedir.
                      </span>
                    </div>
                  )}

                  {reviewError && (
                    <div className="flex items-start justify-between gap-2.5 px-3.5 py-2.5 rounded-xl bg-rose-50 border border-rose-300 text-rose-800 text-xs font-semibold shadow-2xs">
                      <div className="flex items-start gap-2">
                        <ShieldAlert className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                        <span>{reviewError}</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setReviewError(null)}
                        className="text-rose-500 hover:text-rose-700 shrink-0"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}

                  <div className="flex flex-col sm:flex-row gap-2.5">
                    <textarea
                      rows={2}
                      value={comment}
                      onChange={(e) => {
                        setComment(e.target.value);
                        if (reviewError) setReviewError(null);
                      }}
                      placeholder={
                        user
                          ? 'Kitap hakkındaki düşüncelerinizi yazın (opsiyonel, argo/kötü söz içeremez)...'
                          : 'Yorum yapmak için giriş yapmanız gerekmektedir...'
                      }
                      className="flex-1 px-3.5 py-2 rounded-xl border border-slate-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                    <button
                      type="submit"
                      disabled={submittingReview}
                      className="sm:self-end py-2.5 px-4 rounded-xl bg-slate-900 hover:bg-indigo-600 disabled:opacity-60 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors shrink-0 cursor-pointer"
                    >
                      <Send className="w-3.5 h-3.5" />
                      {submittingReview ? 'Gönderiliyor...' : 'Yorumu Gönder'}
                    </button>
                  </div>
                </form>

                {/* Reviews List */}
                {loadingReviews ? (
                  <div className="text-center py-6 text-xs text-slate-400">
                    Değerlendirmeler yükleniyor...
                  </div>
                ) : reviews.length === 0 ? (
                  <div className="text-center py-6 bg-slate-50/50 rounded-xl border border-dashed border-slate-200 text-xs text-slate-500">
                    Bu kitaba henüz değerlendirme yapılmamış. İlk değerlendirmeyi siz yapın!
                  </div>
                ) : (
                  <div className="space-y-2.5 max-h-60 overflow-y-auto pr-1">
                    {reviews.map((rev) => {
                      const isOwnReview = Boolean(
                        user && String(user.id) === String(rev.user_id)
                      );
                      const hasLiked = Boolean(
                        user &&
                          (rev.liked_user_ids || []).some(
                            (uid) => String(uid) === String(user.id)
                          )
                      );
                      const hasDisliked = Boolean(
                        user &&
                          (rev.disliked_user_ids || []).some(
                            (uid) => String(uid) === String(user.id)
                          )
                      );
                      const likesCount = rev.likes_count || 0;
                      const dislikesCount = rev.dislikes_count || 0;

                      return (
                        <div
                          key={rev.id}
                          className="p-3.5 rounded-xl bg-white border border-slate-200/80 shadow-2xs space-y-2"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="inline-flex items-center gap-1 text-xs font-bold text-slate-800">
                                <User className="w-3.5 h-3.5 text-indigo-600" />
                                {rev.user_full_name || 'Okuyucu'}
                              </span>
                              {isOwnReview && (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                                  Sizin Yorumunuz
                                </span>
                              )}
                              <div className="flex items-center gap-0.5 ml-1">
                                {[1, 2, 3, 4, 5].map((s) => (
                                  <Star
                                    key={s}
                                    className={`w-3.5 h-3.5 ${
                                      s <= rev.rating
                                        ? 'text-amber-400 fill-amber-400'
                                        : 'text-slate-200'
                                    }`}
                                  />
                                ))}
                                <span className="ml-1 text-xs font-bold text-slate-700">
                                  {rev.rating}/5
                                </span>
                              </div>
                            </div>

                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-[11px] text-slate-400">
                                {new Date(rev.created_at).toLocaleDateString('tr-TR', {
                                  day: '2-digit',
                                  month: 'short',
                                  year: 'numeric',
                                  hour: '2-digit',
                                  minute: '2-digit',
                                })}
                              </span>

                              {isOwnReview ? (
                                <button
                                  type="button"
                                  onClick={() => handleDeleteReview(rev.id)}
                                  disabled={deletingReviewId === rev.id}
                                  title="Kendi yorumunuzu silin"
                                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-semibold bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 transition-colors disabled:opacity-50 cursor-pointer"
                                >
                                  <Trash2 className="w-3 h-3" />
                                  {deletingReviewId === rev.id ? 'Siliniyor...' : 'Yorumumu Sil'}
                                </button>
                              ) : isAdmin ? (
                                <button
                                  type="button"
                                  onClick={() => handleDeleteReview(rev.id)}
                                  disabled={deletingReviewId === rev.id}
                                  title="Yönetici yetkisiyle bu yorumu silin"
                                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-semibold bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 transition-colors disabled:opacity-50 cursor-pointer"
                                >
                                  <Trash2 className="w-3 h-3" />
                                  {deletingReviewId === rev.id
                                    ? 'Siliniyor...'
                                    : 'Yorumu Sil (Admin)'}
                                </button>
                              ) : null}
                            </div>
                          </div>

                          {rev.comment && (
                            <p className="text-xs text-slate-600 leading-relaxed">{rev.comment}</p>
                          )}

                          <div className="pt-1.5 border-t border-slate-100 flex items-center justify-between gap-2">
                            {!isOwnReview ? (
                              <div className="flex items-center gap-2">
                                <span className="text-[11px] text-slate-400">
                                  Bu yorumu faydalı buldunuz mu?
                                </span>
                                <button
                                  type="button"
                                  onClick={() => handleReactReview(rev.id, 1)}
                                  disabled={reactingReviewId === rev.id}
                                  title="Beğen / Faydalı Buldum (Thumbs Up)"
                                  className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition-colors cursor-pointer disabled:opacity-50 ${
                                    hasLiked
                                      ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
                                      : 'bg-slate-50 hover:bg-emerald-50 text-slate-600 hover:text-emerald-700 border-slate-200'
                                  }`}
                                >
                                  <ThumbsUp
                                    className={`w-3.5 h-3.5 ${
                                      hasLiked ? 'fill-emerald-600 text-emerald-700' : ''
                                    }`}
                                  />
                                  <span>Beğen</span>
                                  <span className="ml-0.5 px-1.5 py-0.2 rounded-full bg-white/80 text-[10px] font-bold">
                                    {likesCount}
                                  </span>
                                </button>

                                <button
                                  type="button"
                                  onClick={() => handleReactReview(rev.id, -1)}
                                  disabled={reactingReviewId === rev.id}
                                  title="Beğenme / Katılmıyorum (Thumbs Down)"
                                  className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition-colors cursor-pointer disabled:opacity-50 ${
                                    hasDisliked
                                      ? 'bg-amber-100 text-amber-900 border-amber-300'
                                      : 'bg-slate-50 hover:bg-amber-50 text-slate-600 hover:text-amber-800 border-slate-200'
                                  }`}
                                >
                                  <ThumbsDown
                                    className={`w-3.5 h-3.5 ${
                                      hasDisliked ? 'fill-amber-600 text-amber-700' : ''
                                    }`}
                                  />
                                  <span>Beğenme</span>
                                  <span className="ml-0.5 px-1.5 py-0.2 rounded-full bg-white/80 text-[10px] font-bold">
                                    {dislikesCount}
                                  </span>
                                </button>
                              </div>
                            ) : (
                              <div className="flex items-center gap-2 text-[11px] text-slate-500">
                                <span>Yorumunuza gelen tepkiler:</span>
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold">
                                  <ThumbsUp className="w-3 h-3" /> {likesCount} Beğeni
                                </span>
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-50 text-amber-700 border border-amber-200 font-semibold">
                                  <ThumbsDown className="w-3 h-3" /> {dislikesCount} Beğenmeme
                                </span>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}

            {/* Kitap Bazlı Okuma Geçmişi Sekmesi */}
            {detailTab === 'reading_history' && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                  <div className="p-3 rounded-xl bg-indigo-50/80 border border-indigo-200 text-center">
                    <span className="block text-[10px] uppercase font-bold text-indigo-600">
                      Toplam Okunma
                    </span>
                    <span className="text-lg font-extrabold text-indigo-950">
                      {bookHistory?.stats?.total_borrow_count || 0} Kez
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-emerald-50/80 border border-emerald-200 text-center">
                    <span className="block text-[10px] uppercase font-bold text-emerald-700">
                      Tamamlanan İade
                    </span>
                    <span className="text-lg font-extrabold text-emerald-950">
                      {bookHistory?.stats?.returned_count || 0}
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-amber-50/80 border border-amber-200 text-center">
                    <span className="block text-[10px] uppercase font-bold text-amber-700">
                      Şu An Okuyan / Onayda
                    </span>
                    <span className="text-lg font-extrabold text-amber-950">
                      {(bookHistory?.stats?.active_borrow_count || 0) +
                        (bookHistory?.stats?.pending_approval_count || 0)}
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-rose-50/80 border border-rose-200 text-center">
                    <span className="block text-[10px] uppercase font-bold text-rose-700">
                      Hasarlı / Kayıp
                    </span>
                    <span className="text-lg font-extrabold text-rose-950">
                      {(bookHistory?.stats?.damaged_count || 0) +
                        (bookHistory?.stats?.lost_count || 0)}
                    </span>
                  </div>
                </div>

                {!bookHistory?.reading_history || bookHistory.reading_history.length === 0 ? (
                  <div className="text-center py-6 bg-slate-50/50 rounded-xl border border-dashed border-slate-200 text-xs text-slate-500">
                    Bu kitap henüz hiçbir üye tarafından ödünç alınmamış.
                  </div>
                ) : (
                  <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                    {bookHistory.reading_history.map((rec) => {
                      const isOwn = user && String(user.id) === String(rec.user_id);
                      const displayReader =
                        isAdmin || isOwn
                          ? rec.reader_name
                          : rec.reader_name
                              .split(' ')
                              .map((part) => (part ? `${part[0]}***` : ''))
                              .join(' ');
                      return (
                        <div
                          key={rec.borrowing_id}
                          className="p-3 rounded-xl bg-white border border-slate-200/90 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs"
                        >
                          <div className="space-y-0.5">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-bold text-slate-800 flex items-center gap-1">
                                <User className="w-3.5 h-3.5 text-indigo-600" />
                                {displayReader}
                              </span>
                              {isOwn && (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                                  Siz
                                </span>
                              )}
                              {rec.approval_status === 'PENDING_BORROW' ? (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
                                  Ödünç Onayı Bekliyor
                                </span>
                              ) : rec.approval_status === 'PENDING_RETURN' ? (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 text-purple-800 border border-purple-300">
                                  İade Kontrolünde
                                </span>
                              ) : rec.approval_status === 'REJECTED' ? (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-600 border border-slate-300">
                                  İptal / Reddedildi
                                </span>
                              ) : rec.status === 'RETURNED' ? (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                                  Okundu & İade Edildi
                                </span>
                              ) : (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-sky-100 text-sky-800 border border-sky-300">
                                  Şu An Okuyor
                                </span>
                              )}

                              {rec.return_condition === 'DAMAGED' && (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-300">
                                  Hasarlı ({rec.damage_penalty} TL)
                                </span>
                              )}
                              {rec.return_condition === 'LOST' && (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-900 border border-rose-300">
                                  Kayıp ({rec.damage_penalty} TL)
                                </span>
                              )}
                            </div>
                            {(rec.return_notes || rec.admin_notes) && (
                              <p className="text-[11px] text-slate-500">
                                {rec.admin_notes ? `Görevli Notu: ${rec.admin_notes}` : `Not: ${rec.return_notes}`}
                              </p>
                            )}
                          </div>
                          <div className="text-[11px] text-slate-500 sm:text-right shrink-0">
                            <div>
                              Ödünç: <strong>{rec.borrow_date}</strong> • Son Teslim:{' '}
                              <strong>{rec.due_date}</strong>
                            </div>
                            {rec.return_date && (
                              <div className="text-emerald-700 font-semibold">
                                İade Tarihi: {rec.return_date}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* Geçmiş Stok Hareketleri ve Hasar/Kayıp Raporları Sekmesi */}
            {detailTab === 'stock_history' && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                  <div className="p-3 rounded-xl bg-slate-100 border border-slate-200 text-center">
                    <span className="block text-[10px] uppercase font-bold text-slate-500">
                      Güncel Raftaki Stok
                    </span>
                    <span className="text-lg font-extrabold text-slate-900">
                      {book.stock_count} Adet
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-amber-50/80 border border-amber-200 text-center">
                    <span className="block text-[10px] uppercase font-bold text-amber-700">
                      Hasar Raporu
                    </span>
                    <span className="text-lg font-extrabold text-amber-950">
                      {bookHistory?.stats?.damaged_count || 0} Adet
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-rose-50/80 border border-rose-200 text-center">
                    <span className="block text-[10px] uppercase font-bold text-rose-700">
                      Kayıp Raporu
                    </span>
                    <span className="text-lg font-extrabold text-rose-950">
                      {bookHistory?.stats?.lost_count || 0} Adet
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-indigo-50/80 border border-indigo-200 text-center">
                    <span className="block text-[10px] uppercase font-bold text-indigo-700">
                      Hasar/Kayıp Tazminatı
                    </span>
                    <span className="text-lg font-extrabold text-indigo-950">
                      {(bookHistory?.stats?.total_damage_loss_penalty || 0).toFixed(0)} TL
                    </span>
                  </div>
                </div>

                {!bookHistory?.stock_movements || bookHistory.stock_movements.length === 0 ? (
                  <div className="text-center py-6 bg-slate-50/50 rounded-xl border border-dashed border-slate-200 text-xs text-slate-500">
                    Bu kitap için henüz kayıtlı bir stok hareketi veya hasar/kayıp raporu bulunmuyor.
                  </div>
                ) : (
                  <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                    {bookHistory.stock_movements.map((mov) => (
                      <div
                        key={mov.id}
                        className={`p-3 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs ${
                          mov.condition === 'LOST'
                            ? 'bg-rose-50/60 border-rose-200'
                            : mov.condition === 'DAMAGED'
                            ? 'bg-amber-50/60 border-amber-200'
                            : 'bg-white border-slate-200/90'
                        }`}
                      >
                        <div className="space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            {mov.condition === 'LOST' ? (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-rose-600 text-white">
                                KAYIP RAPORU
                              </span>
                            ) : mov.condition === 'DAMAGED' ? (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-amber-600 text-white">
                                HASAR RAPORU
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                                SAĞLAM / STOK HAREKETİ
                              </span>
                            )}
                            <span className="font-bold text-slate-800">
                              {mov.movement_type === 'BORROW_REQUEST'
                                ? 'Ödünç Talebi (Stok Ayrıldı)'
                                : mov.movement_type === 'BORROW_APPROVED'
                                ? 'Görevli Ödünç Teslim Onayı'
                                : mov.movement_type === 'BORROW_REJECTED'
                                ? 'Ödünç Talebi İptal/Red (Stok İade)'
                                : mov.movement_type === 'BORROW_DIRECT'
                                ? 'Ödünç Alındı'
                                : mov.movement_type === 'RETURN_GOOD'
                                ? 'Sağlam İade Alındı'
                                : mov.movement_type === 'RETURN_DAMAGED'
                                ? 'Hasarlı Kitap İadesi'
                                : mov.movement_type === 'RETURN_LOST'
                                ? 'Kayıp Kitap Bildirimi'
                                : mov.movement_type === 'ADMIN_DAMAGE'
                                ? 'Envanter Hasar Düşümü'
                                : mov.movement_type === 'ADMIN_LOST'
                                ? 'Envanter Kayıp Düşümü'
                                : 'Yeni Stok Girişi'}
                            </span>
                            {mov.penalty_added > 0 && (
                              <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-300">
                                +{mov.penalty_added} TL Tazminat
                              </span>
                            )}
                          </div>
                          {mov.notes && <p className="text-[11px] text-slate-600">{mov.notes}</p>}
                        </div>

                        <div className="sm:text-right shrink-0 space-y-0.5">
                          <div className="font-mono font-bold text-xs">
                            Stok: {mov.stock_before} → {mov.stock_after}{' '}
                            <span
                              className={
                                mov.quantity_change > 0
                                  ? 'text-emerald-600'
                                  : mov.quantity_change < 0
                                  ? 'text-rose-600'
                                  : 'text-slate-500'
                              }
                            >
                              ({mov.quantity_change > 0 ? `+${mov.quantity_change}` : mov.quantity_change})
                            </span>
                          </div>
                          <div className="text-[10px] text-slate-400">
                            {new Date(mov.created_at).toLocaleString('tr-TR')}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

