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

  // Default due_date = today + 14 days
  const getDefaultDueDate = () => {
    const d = new Date();
    d.setDate(d.getDate() + 14);
    return d.toISOString().split('T')[0];
  };
  const todayStr = new Date().toISOString().split('T')[0];

  const [dueDate, setDueDate] = useState(getDefaultDueDate());
  const [actionLoading, setActionLoading] = useState(false);

  // Review form state
  const [rating, setRating] = useState(5);
  const [hoverRating, setHoverRating] = useState(0);
  const [comment, setComment] = useState('');
  const [submittingReview, setSubmittingReview] = useState(false);

  const loadBookAndReviews = async () => {
    setLoadingReviews(true);
    try {
      const [freshBook, bookReviews] = await Promise.all([
        api.getBook(initialBook.id),
        api.getReviews(initialBook.id),
      ]);
      setBook(freshBook);
      setReviews(bookReviews || []);
    } catch (err) {
      notify(err.message || 'Kitap detayları yüklenemedi', 'error');
    } finally {
      setLoadingReviews(false);
    }
  };

  useEffect(() => {
    loadBookAndReviews();
  }, [initialBook.id]);

  const handleBorrow = async () => {
    if (!user) {
      notify('Kitap ödünç almak için lütfen giriş yapın.', 'info');
      onClose();
      onOpenAuth('login');
      return;
    }

    setActionLoading(true);
    try {
      await api.borrowBook({
        book_id: book.id,
        due_date: dueDate,
      });
      notify(`"${book.title}" başarıyla ödünç alındı!`, 'success');
      await loadBookAndReviews();
      if (onBookUpdated) onBookUpdated();
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

    setActionLoading(true);
    try {
      const res = await api.createReservation({
        book_id: book.id,
      });
      notify(
        res?.queue_message || `"${book.title}" için rezervasyon sırasına girdiniz.`,
        'success'
      );
      await loadBookAndReviews();
      if (onBookUpdated) onBookUpdated();
    } catch (err) {
      notify(err.message || 'Rezervasyon oluşturulamadı', 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReviewSubmit = async (e) => {
    e.preventDefault();
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
      const updatedReviews = await api.getReviews(book.id);
      setReviews(updatedReviews || []);
    } catch (err) {
      notify(err.message || 'Değerlendirme gönderilemedi', 'error');
    } finally {
      setSubmittingReview(false);
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
            {/* Left Cover Visual */}
            <div className="flex flex-col items-center justify-center p-6 rounded-xl bg-gradient-to-br from-indigo-600 via-indigo-700 to-violet-800 text-white shadow-inner text-center">
              <BookOpen className="w-14 h-14 mb-3 opacity-90" />
              <h3 className="font-bold text-sm line-clamp-2">{book.title}</h3>
              <span className="mt-2 px-2.5 py-0.5 rounded-full text-[11px] bg-white/20 backdrop-blur-xs font-medium">
                {book.published_year || 'Yıl Belirtilmemiş'}
              </span>
              {averageRating && (
                <div className="mt-3 inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-amber-400/20 border border-amber-300/30 text-amber-200 text-xs font-bold">
                  <Star className="w-3.5 h-3.5 fill-amber-300 text-amber-300" />
                  <span>{averageRating} / 5.0</span>
                  <span className="text-[10px] opacity-80">({reviews.length})</span>
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
              <div className="pt-3 border-t border-slate-200/80">
                {userHasActiveSlot ? (
                  <div className="space-y-3">
                    <div className="bg-emerald-50 border border-emerald-200 p-3 rounded-xl text-xs text-emerald-900">
                      <p className="font-bold flex items-center gap-1.5">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                        Rezerve sırası sizde ({userQueuePos}. sıradasınız)!
                      </p>
                      <p className="text-emerald-700 mt-0.5">
                        Kitap stoğu 24 saatliğine sizin için ayrıldı. Süreniz dolmadan hemen ödünç alabilirsiniz; ödünç aldığınızda rezerve listesinden otomatik silinir.
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
                        onClick={handleBorrow}
                        disabled={actionLoading}
                        className="py-2.5 px-5 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white font-semibold text-sm shadow-sm flex items-center justify-center gap-2 transition-all cursor-pointer"
                      >
                        <BookOpen className="w-4 h-4" />
                        {actionLoading ? 'İşleniyor...' : 'Rezerve Kitabı Ödünç Al'}
                      </button>
                    </div>
                  </div>
                ) : userQueuePos !== null ? (
                  <div className="bg-amber-50/90 border border-amber-200 p-3.5 rounded-xl text-xs text-amber-900 space-y-1">
                    <p className="font-bold flex items-center gap-1.5">
                      <Clock className="w-4 h-4 text-amber-600 shrink-0" />
                      Rezerve listesinde {userQueuePos}. sıradasınız
                      {userQueuePos > 1 ? ` (Önünüzde ${userQueuePos - 1} kişi var)` : ''}
                    </p>
                    <p className="text-amber-800 leading-relaxed">
                      {userQueuePos > 1
                        ? `Rezerve listesinde ${userQueuePos}. sıradasınız. Diğer kullanıcılar süreleri bitene kadar ödünç almazlarsa ödünç alabilirsiniz.`
                        : 'Kitabı rezerve ettiniz; stok olduğunda kitabı ödünç almak için 24 saatlik süreniz başlar.'}
                    </p>
                  </div>
                ) : allStockReservedByOthers ? (
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 bg-amber-50/80 border border-amber-200 p-3.5 rounded-xl">
                    <div className="text-xs text-amber-900">
                      <p className="font-bold">
                        Stokta {book.stock_count} adet var ancak şu an başkasına rezerve edilmiş durumda!
                      </p>
                      <p className="text-amber-700 mt-0.5">
                        Rezerve eden kullanıcıların 24 saatlik süresi bitene kadar başka kullanıcı ödünç alamaz, sadece rezerve ederek sıraya girebilirsiniz (Sırada: {reservedCount} kişi).
                      </p>
                    </div>
                    <button
                      onClick={handleReserve}
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
                        onClick={handleBorrow}
                        disabled={actionLoading}
                        className="py-2.5 px-5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white font-semibold text-sm shadow-sm shadow-indigo-200 flex items-center justify-center gap-2 transition-all cursor-pointer"
                      >
                        <BookOpen className="w-4 h-4" />
                        {actionLoading ? 'İşleniyor...' : 'Ödünç Al'}
                      </button>
                      <button
                        onClick={handleReserve}
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
                      onClick={handleReserve}
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
              </div>
            </div>
          </div>

          {/* Reviews & Rating Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-slate-200 pb-2.5">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <Star className="w-5 h-5 text-amber-500 fill-amber-400" />
                Okuyucu Değerlendirmeleri ({reviews.length})
              </h3>
              {averageRating && (
                <span className="text-xs font-bold text-slate-600 bg-slate-100 px-2.5 py-1 rounded-lg">
                  Ortalama Puan: {averageRating} / 5
                </span>
              )}
            </div>

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

              <div className="flex flex-col sm:flex-row gap-2.5">
                <textarea
                  rows={2}
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder={
                    user
                      ? 'Kitap hakkındaki düşüncelerinizi yazın (opsiyonel)...'
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
                {reviews.map((rev) => (
                  <div
                    key={rev.id}
                    className="p-3.5 rounded-xl bg-white border border-slate-200/80 shadow-2xs space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1">
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
                        <span className="ml-1.5 text-xs font-bold text-slate-700">
                          {rev.rating}/5
                        </span>
                      </div>
                      <span className="text-[11px] text-slate-400">
                        {new Date(rev.created_at).toLocaleDateString('tr-TR', {
                          day: '2-digit',
                          month: 'short',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>
                    {rev.comment && (
                      <p className="text-xs text-slate-600 leading-relaxed">{rev.comment}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

