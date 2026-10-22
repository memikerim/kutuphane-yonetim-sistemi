import React, { useState } from 'react';
import {
  Library,
  BookOpen,
  BookmarkCheck,
  ShieldCheck,
  LogIn,
  UserPlus,
  LogOut,
  Menu,
  X,
  User as UserIcon,
} from 'lucide-react';

export default function Navbar({
  activeTab,
  setActiveTab,
  user,
  onOpenAuth,
  onLogout,
}) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const isAdmin = user?.roles?.includes('ADMIN');

  const handleNavClick = (tab) => {
    setActiveTab(tab);
    setMobileMenuOpen(false);
  };

  return (
    <>
      <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-md border-b border-slate-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Brand Logo */}
            <button
              onClick={() => handleNavClick('catalog')}
              className="flex items-center gap-2.5 text-left group focus:outline-none"
            >
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 flex items-center justify-center text-white shadow-md shadow-indigo-200 group-hover:scale-105 transition-transform">
                <Library className="w-5 h-5" />
              </div>
              <div>
                <span className="text-lg font-bold bg-gradient-to-r from-slate-900 to-indigo-900 bg-clip-text text-transparent block leading-none">
                  Kütüphane
                </span>
                <span className="text-[11px] font-medium text-slate-500 tracking-wide">
                  YÖNETİM SİSTEMİ
                </span>
              </div>
            </button>

            {/* Desktop Navigation Links */}
            <nav className="hidden md:flex items-center gap-1.5">
              <button
                onClick={() => handleNavClick('catalog')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  activeTab === 'catalog'
                    ? 'bg-indigo-50 text-indigo-700 shadow-sm ring-1 ring-indigo-200/60'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`}
              >
                <BookOpen className="w-4 h-4" />
                Katalog Vitrini
              </button>

              {user && (
                <button
                  onClick={() => handleNavClick('mylibrary')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    activeTab === 'mylibrary'
                      ? 'bg-indigo-50 text-indigo-700 shadow-sm ring-1 ring-indigo-200/60'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`}
                >
                  <BookmarkCheck className="w-4 h-4" />
                  Kitaplarım & Rezervasyonlarım
                </button>
              )}

              {isAdmin && (
                <button
                  onClick={() => handleNavClick('admin')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    activeTab === 'admin'
                      ? 'bg-amber-50 text-amber-800 shadow-sm ring-1 ring-amber-300/60'
                      : 'text-amber-700 hover:bg-amber-50/70'
                  }`}
                >
                  <ShieldCheck className="w-4 h-4" />
                  Admin Paneli
                </button>
              )}
            </nav>

            {/* Desktop User Profile / Auth Buttons */}
            <div className="hidden md:flex items-center gap-3">
              {user ? (
                <div className="flex items-center gap-3 pl-3 border-l border-slate-200">
                  <div className="flex items-center gap-2.5 bg-slate-50 border border-slate-200/80 px-3 py-1.5 rounded-xl">
                    <div className="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-700 flex items-center justify-center font-semibold text-sm">
                      {user.first_name?.[0]?.toUpperCase()}
                      {user.last_name?.[0]?.toUpperCase()}
                    </div>
                    <div className="text-left">
                      <div className="text-xs font-semibold text-slate-800 leading-tight">
                        {user.first_name} {user.last_name}
                      </div>
                      <div className="flex items-center gap-1 mt-0.5">
                        {isAdmin ? (
                          <span className="inline-flex items-center px-1.5 py-0.2 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
                            ADMIN
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-1.5 py-0.2 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
                            USER
                          </span>
                        )}
                        <span className="text-[10px] text-slate-400 truncate max-w-[120px]">
                          {user.email}
                        </span>
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={onLogout}
                    title="Çıkış Yap"
                    className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold text-rose-600 hover:bg-rose-50 border border-transparent hover:border-rose-200 transition-colors"
                  >
                    <LogOut className="w-4 h-4" />
                    <span>Çıkış</span>
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => onOpenAuth('login')}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-100 transition-colors"
                  >
                    <LogIn className="w-4 h-4" />
                    Giriş Yap
                  </button>
                  <button
                    onClick={() => onOpenAuth('register')}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm shadow-indigo-200 transition-all"
                  >
                    <UserPlus className="w-4 h-4" />
                    Kayıt Ol
                  </button>
                </div>
              )}
            </div>

            {/* Mobile Hamburger Button */}
            <div className="flex items-center md:hidden">
              <button
                onClick={() => setMobileMenuOpen(true)}
                aria-label="Menüyü Aç"
                className="p-2 rounded-xl text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <Menu className="w-6 h-6" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Mobile Drawer / Sidebar */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs transition-opacity"
            onClick={() => setMobileMenuOpen(false)}
          />

          {/* Drawer Content */}
          <div className="relative ml-auto w-80 max-w-[85vw] bg-white h-full shadow-2xl flex flex-col justify-between z-10 overflow-y-auto">
            <div className="p-5">
              {/* Drawer Header */}
              <div className="flex items-center justify-between pb-4 border-b border-slate-100">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center text-white">
                    <Library className="w-5 h-5" />
                  </div>
                  <span className="font-bold text-slate-900">Menü</span>
                </div>
                <button
                  onClick={() => setMobileMenuOpen(false)}
                  className="p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Mobile User Card */}
              {user ? (
                <div className="mt-4 p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center font-bold">
                      {user.first_name?.[0]?.toUpperCase()}
                      {user.last_name?.[0]?.toUpperCase()}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-bold text-slate-900 truncate">
                        {user.first_name} {user.last_name}
                      </p>
                      <p className="text-xs text-slate-500 truncate">{user.email}</p>
                    </div>
                  </div>
                  <div className="mt-3 flex items-center gap-2">
                    <span className="text-xs text-slate-500">Yetki Rolü:</span>
                    {user.roles?.map((r) => (
                      <span
                        key={r}
                        className={`px-2 py-0.5 rounded-md text-[11px] font-bold ${
                          r === 'ADMIN'
                            ? 'bg-amber-100 text-amber-800 border border-amber-300'
                            : 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                        }`}
                      >
                        {r}
                      </span>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="mt-4 p-4 rounded-2xl bg-indigo-50/70 border border-indigo-100 text-center">
                  <UserIcon className="w-8 h-8 text-indigo-500 mx-auto mb-1.5" />
                  <p className="text-xs text-slate-600 mb-3">
                    Kitap ödünç almak, rezerve etmek veya yorum yapmak için giriş yapın.
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => {
                        setMobileMenuOpen(false);
                        onOpenAuth('login');
                      }}
                      className="py-2 px-3 rounded-xl text-xs font-semibold bg-white text-slate-700 border border-slate-200 hover:bg-slate-50"
                    >
                      Giriş Yap
                    </button>
                    <button
                      onClick={() => {
                        setMobileMenuOpen(false);
                        onOpenAuth('register');
                      }}
                      className="py-2 px-3 rounded-xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700"
                    >
                      Kayıt Ol
                    </button>
                  </div>
                </div>
              )}

              {/* Mobile Navigation Links */}
              <div className="mt-6 space-y-1.5">
                <p className="px-3 text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2">
                  Sayfalar
                </p>
                <button
                  onClick={() => handleNavClick('catalog')}
                  className={`w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition-colors ${
                    activeTab === 'catalog'
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  <BookOpen className="w-5 h-5" />
                  Katalog Vitrini
                </button>

                {user && (
                  <button
                    onClick={() => handleNavClick('mylibrary')}
                    className={`w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition-colors ${
                      activeTab === 'mylibrary'
                        ? 'bg-indigo-600 text-white shadow-sm'
                        : 'text-slate-700 hover:bg-slate-100'
                    }`}
                  >
                    <BookmarkCheck className="w-5 h-5" />
                    Kitaplarım & Rezervasyonlarım
                  </button>
                )}

                {isAdmin && (
                  <button
                    onClick={() => handleNavClick('admin')}
                    className={`w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition-colors ${
                      activeTab === 'admin'
                        ? 'bg-amber-600 text-white shadow-sm'
                        : 'text-amber-800 bg-amber-50/60 hover:bg-amber-100'
                    }`}
                  >
                    <ShieldCheck className="w-5 h-5" />
                    Yönetim Paneli (Admin)
                  </button>
                )}
              </div>
            </div>

            {/* Mobile Drawer Footer */}
            {user && (
              <div className="p-5 border-t border-slate-100">
                <button
                  onClick={() => {
                    setMobileMenuOpen(false);
                    onLogout();
                  }}
                  className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-sm font-semibold text-rose-600 bg-rose-50 hover:bg-rose-100 transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  Oturumu Kapat
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

