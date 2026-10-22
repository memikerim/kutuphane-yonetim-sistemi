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
} from 'lucide-react';
import { api } from '../api';

export default function MyLibraryView({ notify, onSelectBook }) {
  const [borrowings, setBorrowings] = useState([]);
  const [reservations, setReservations] = useState([]);
  const [bookMap, setBookMap] = useState({});
  const [loading, setLoading] = useState(true);
  const [returningId, setReturningId] = useState(null);
  const [subTab, setSubTab] = useState('borrowings');

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

  const handleReturnBook = async (borrowingId) => {
    setReturningId(borrowingId);
    try {
      await api.returnBook(borrowingId);
      notify('Kitap başarıyla iade edildi ve stok 1 artırıldı!', 'success');
      await fetchAll();
    } catch (err) {
      notify(err.message || 'İade işlemi başarısız', 'error');
    } finally {
      setReturningId(null);
    }
  };

  const activeBorrowingsCount = borrowings.filter((b) => b.status === 'ACTIVE').length;
  const pendingReservationsCount = reservations.filter((r) => r.status === 'PENDING').length;

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-white rounded-2xl p-5 sm:p-6 border border-slate-200/80 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900 flex items-center gap-2.5">
            <BookmarkCheck className="w-6 h-6 text-indigo-600" />
            Kitaplarım & Rezervasyonlarım
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Ödünç aldığınız kitapları görüntüleyip tek tıkla iade edebilir ve rezervasyon sıranızı takip edebilirsiniz.
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
              const isOverdue =
                !isReturned && new Date(item.due_date) < new Date(new Date().toDateString());

              return (
                <div
                  key={item.id}
                  className="bg-white rounded-2xl p-5 border border-slate-200/90 shadow-2xs flex flex-col justify-between gap-4 hover:border-indigo-200 transition-all"
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
                        <span className="shrink-0 inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300">
                          <AlertCircle className="w-3.5 h-3.5" />
                          Süresi Geçti
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
                      <div className="bg-slate-50 p-2.5 rounded-xl">
                        <span className="text-slate-400 block text-[11px]">Son Teslim Tarihi</span>
                        <span className="font-semibold text-slate-700 flex items-center gap-1 mt-0.5">
                          <Calendar className="w-3.5 h-3.5 text-amber-500" />
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
                  </div>

                  {!isReturned && (
                    <div className="pt-2 flex justify-end">
                      <button
                        onClick={() => handleReturnBook(item.id)}
                        disabled={returningId === item.id}
                        className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white text-xs font-semibold shadow-xs transition-all cursor-pointer"
                      >
                        <RotateCcw className="w-4 h-4" />
                        {returningId === item.id ? 'İade Ediliyor...' : 'Kitabı İade Et'}
                      </button>
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
          <h3 className="text-base font-bold text-slate-800">Aktif veya geçmiş rezervasyonunuz yok</h3>
          <p className="text-xs text-slate-500 mt-1">
            Stokta olmayan veya sıraya girmek istediğiniz kitapları detay ekranından rezerve edebilirsiniz.
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-2xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3.5 px-4">Kitap</th>
                  <th className="py-3.5 px-4">ISBN</th>
                  <th className="py-3.5 px-4">Rezervasyon Tarihi</th>
                  <th className="py-3.5 px-4">Durum</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {reservations.map((res) => {
                  const book = bookMap[res.book_id];
                  return (
                    <tr key={res.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3.5 px-4 font-semibold text-slate-900">
                        <button
                          onClick={() => book && onSelectBook(book)}
                          className="hover:text-indigo-600 text-left cursor-pointer"
                        >
                          {book ? book.title : `Kitap #${res.book_id.slice(0, 8)}`}
                        </button>
                      </td>
                      <td className="py-3.5 px-4 text-xs font-mono text-slate-500">
                        {book ? book.isbn : '-'}
                      </td>
                      <td className="py-3.5 px-4 text-xs text-slate-600">
                        {new Date(res.reservation_date).toLocaleString('tr-TR')}
                      </td>
                      <td className="py-3.5 px-4">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${
                            res.status === 'PENDING'
                              ? 'bg-amber-100 text-amber-800 border border-amber-300'
                              : res.status === 'FULFILLED'
                              ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                              : 'bg-slate-100 text-slate-600'
                          }`}
                        >
                          {res.status === 'PENDING'
                            ? 'PENDING (Sırada Bekliyor)'
                            : res.status}
                        </span>
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

