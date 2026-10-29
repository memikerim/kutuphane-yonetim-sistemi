import React, { useState, useRef, useEffect } from 'react';
import {
  Bell,
  Clock,
  AlertTriangle,
  CheckCircle2,
  BookmarkPlus,
  ShieldAlert,
  ArrowRight,
  X,
  CreditCard,
  BookOpen,
  RotateCcw,
} from 'lucide-react';

export default function NotificationCenter({
  notifications,
  user,
  isAdmin,
  onNotificationAction,
}) {
  const [open, setOpen] = useState(false);
  const [filterTab, setFilterTab] = useState('ALL'); // 'ALL' | 'ADMIN' | 'USER'
  const popoverRef = useRef(null);

  const totalCount = notifications?.total_count || 0;
  const adminCount = notifications?.admin_action_count || 0;
  const userCount = notifications?.user_action_count || 0;
  const items = notifications?.items || [];

  // Popover dışına tıklandığında veya ESC tuşuna basıldığında menüyü kapat
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (popoverRef.current && !popoverRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };

    if (open) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  const filteredItems = items.filter((item) => {
    if (filterTab === 'ADMIN') return item.target === 'ADMIN';
    if (filterTab === 'USER') return item.target === 'USER';
    return true;
  });

  const getItemBadge = (item) => {
    switch (item.type) {
      case 'RESERVATION_READY':
        return { label: 'Rezervasyon Sırası', bg: 'bg-emerald-100 text-emerald-800 border-emerald-300' };
      case 'PENALTY_DUE':
        return { label: 'Borç & Ceza', bg: 'bg-rose-100 text-rose-800 border-rose-300' };
      case 'PAYMENT_PENDING_APPROVAL':
        return { label: 'Ödeme Onayı Bekliyor', bg: 'bg-purple-100 text-purple-900 border-purple-300' };
      case 'OVERDUE_BOOK':
        return { label: 'Gecikmiş Kitap', bg: 'bg-red-100 text-red-800 border-red-300' };
      case 'PENDING_BORROW':
        return { label: 'Ödünç Talebi', bg: 'bg-blue-100 text-blue-800 border-blue-300' };
      case 'PENDING_RETURN':
        return { label: 'İade Kontrolü', bg: 'bg-amber-100 text-amber-800 border-amber-300' };
      case 'BORROW_REJECTED':
        return { label: 'Ödünç Reddedildi', bg: 'bg-rose-100 text-rose-900 border-rose-300 font-extrabold' };
      case 'BANNED':
        return { label: 'Hesap Kısıtlaması', bg: 'bg-rose-600 text-white border-rose-700' };
      case 'ADMIN_PENDING_PAYMENT':
        return { label: 'Yönetici: Ödeme Onayı', bg: 'bg-purple-600 text-white border-purple-700' };
      case 'ADMIN_PENDING_RETURN':
        return { label: 'Yönetici: İade Onayı', bg: 'bg-amber-500 text-white border-amber-600' };
      case 'ADMIN_PENDING_BORROW':
        return { label: 'Yönetici: Ödünç Onayı', bg: 'bg-indigo-600 text-white border-indigo-700' };
      default:
        return { label: 'Bildirim', bg: 'bg-slate-100 text-slate-800 border-slate-300' };
    }
  };

  const getItemIcon = (item) => {
    if (item.severity === 'error') {
      return <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />;
    }
    if (item.severity === 'warning') {
      return <Clock className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />;
    }
    if (item.severity === 'success') {
      return <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />;
    }
    return <Bell className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />;
  };

  const getActionLabel = (item) => {
    switch (item.action_type) {
      case 'BORROW_RESERVED':
        return 'Kitabı Ödünç Al';
      case 'PAY_PENALTY':
        return 'Borcu İncele & Öde';
      case 'RETURN_BOOK':
        return 'Kitaplarımı Görüntüle';
      case 'VIEW_PAYMENT_STATUS':
        return 'Durumu Gör';
      case 'ADMIN_APPROVE_PAYMENT':
        return 'Ödemeyi Onayla & Kapat';
      case 'ADMIN_APPROVE_RETURN':
        return 'İadeyi İncele & Onayla';
      case 'ADMIN_APPROVE_BORROW':
        return 'Ödüncü Onayla & Teslim Et';
      default:
        return 'Detayı İncele';
    }
  };

  const handleCardClick = (item) => {
    setOpen(false);
    if (onNotificationAction) {
      onNotificationAction(item);
    }
  };

  return (
    <div className="relative" ref={popoverRef}>
      {/* Navbar Notification Trigger Button */}
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-label="Bildirimler ve Bekleyen Aksiyonlar"
        className={`relative flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
          totalCount > 0
            ? 'bg-rose-50 text-rose-700 border border-rose-300 shadow-2xs hover:bg-rose-100/80'
            : 'bg-slate-50 text-slate-700 border border-slate-200 hover:bg-slate-100'
        }`}
      >
        <div className="relative">
          <Bell className={`w-4 h-4 ${totalCount > 0 ? 'text-rose-600' : 'text-slate-600'}`} />
          {totalCount > 0 && (
            <span className="absolute -top-1.5 -right-1.5 flex h-3.5 w-3.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-rose-600 text-[9px] font-extrabold text-white items-center justify-center">
                {totalCount > 9 ? '9+' : totalCount}
              </span>
            </span>
          )}
        </div>
        <span className="hidden sm:inline">Bildirimler</span>
        {totalCount > 0 && (
          <span className="inline-flex items-center px-1.5 py-0.2 rounded-full text-[10px] font-black bg-rose-600 text-white">
            {totalCount}
          </span>
        )}
      </button>

      {/* Popover Dropdown Panel */}
      {open && (
        <div className="absolute right-0 mt-2 w-80 sm:w-96 max-w-[92vw] bg-white rounded-2xl shadow-2xl border border-slate-200 z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-150">
          {/* Header */}
          <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white p-3.5 sm:p-4 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-xl bg-white/10 flex items-center justify-center">
                <Bell className="w-4 h-4 text-amber-300" />
              </div>
              <div>
                <h3 className="text-xs sm:text-sm font-extrabold leading-tight">
                  Bildirimler & Aksiyon Merkezi
                </h3>
                <span className="text-[11px] text-slate-300">
                  {totalCount > 0
                    ? `${totalCount} adet aksiyon gerektiren durum var`
                    : 'Bekleyen yeni bildiriminiz yok'}
                </span>
              </div>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="p-1 rounded-lg text-slate-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Admin / User Filter Tabs (Eğer kullanıcı admin ise) */}
          {isAdmin && (
            <div className="flex items-center gap-1 p-2 bg-slate-100 border-b border-slate-200 text-xs font-bold">
              <button
                onClick={() => setFilterTab('ALL')}
                className={`flex-1 py-1 rounded-lg transition-all cursor-pointer ${
                  filterTab === 'ALL'
                    ? 'bg-white text-slate-900 shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Tümü ({totalCount})
              </button>
              <button
                onClick={() => setFilterTab('ADMIN')}
                className={`flex-1 py-1 rounded-lg transition-all cursor-pointer ${
                  filterTab === 'ADMIN'
                    ? 'bg-amber-600 text-white shadow-2xs'
                    : 'text-amber-800 hover:text-amber-950'
                }`}
              >
                Yönetici ({adminCount})
              </button>
              <button
                onClick={() => setFilterTab('USER')}
                className={`flex-1 py-1 rounded-lg transition-all cursor-pointer ${
                  filterTab === 'USER'
                    ? 'bg-indigo-600 text-white shadow-2xs'
                    : 'text-indigo-700 hover:text-indigo-950'
                }`}
              >
                Kişisel ({userCount})
              </button>
            </div>
          )}

          {/* Notification Items List */}
          <div className="max-h-80 sm:max-h-96 overflow-y-auto divide-y divide-slate-100 p-2 space-y-1.5">
            {filteredItems.length === 0 ? (
              <div className="p-6 text-center space-y-2">
                <div className="w-10 h-10 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
                <p className="text-xs font-bold text-slate-800">
                  Aksiyon Gerektiren Bildirim Yok
                </p>
                <p className="text-[11px] text-slate-500">
                  Tüm kitaplarınız, rezervasyonlarınız ve onay süreçleriniz sorunsuz ve güncel durumdadır.
                </p>
              </div>
            ) : (
              filteredItems.map((item) => {
                const badge = getItemBadge(item);
                const actionLabel = getActionLabel(item);

                return (
                  <div
                    key={item.id}
                    onClick={() => handleCardClick(item)}
                    className="p-3 rounded-xl bg-slate-50/70 hover:bg-indigo-50/80 border border-slate-200/80 hover:border-indigo-300 transition-all cursor-pointer group space-y-1.5"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-start gap-2">
                        {getItemIcon(item)}
                        <div>
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span
                              className={`px-1.5 py-0.2 rounded-md text-[10px] font-extrabold border ${badge.bg}`}
                            >
                              {badge.label}
                            </span>
                          </div>
                          <h4 className="text-xs font-bold text-slate-900 mt-1 leading-snug group-hover:text-indigo-700">
                            {item.title}
                          </h4>
                        </div>
                      </div>
                    </div>

                    <p className="text-[11px] text-slate-600 leading-relaxed pl-6">
                      {item.message}
                    </p>

                    <div className="flex items-center justify-end pt-1">
                      <span className="inline-flex items-center gap-1 text-[11px] font-extrabold text-indigo-600 group-hover:text-indigo-800">
                        <span>{actionLabel}</span>
                        <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Footer */}
          {filteredItems.length > 0 && (
            <div className="p-2.5 bg-slate-50 border-t border-slate-200 text-center">
              <span className="text-[10px] font-medium text-slate-500">
                Bildirime tıklayarak doğrudan ilgili işlem ve onay kuyruğuna gidebilirsiniz.
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

