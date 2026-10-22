import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, X, Search, Check } from 'lucide-react';

/**
 * Katalog filtreleme alanında kullanılan, içine yazılarak arama yapılabilen
 * (Searchable Combobox) akıllı seçim bileşeni.
 */
export default function SearchableFilterSelect({
  label,
  placeholder = 'Tümü (Ara veya Seç)...',
  options = [], // [{ label: '...', value: '...' }]
  value,
  onChange,
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const containerRef = useRef(null);

  // Dışarı tıklanınca açılır menüyü kapat
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const selectedOption = options.find((opt) => opt.value === value);

  const filteredOptions = options.filter((opt) =>
    opt.label.toLowerCase().includes(query.trim().toLowerCase())
  );

  const handleSelect = (val) => {
    onChange(val);
    setQuery('');
    setOpen(false);
  };

  return (
    <div ref={containerRef} className="relative">
      {label && (
        <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1">
          {label}
        </label>
      )}

      {/* Trigger / Input Box */}
      <div
        onClick={() => setOpen(true)}
        className={`flex items-center justify-between px-3 py-2 rounded-xl border text-xs sm:text-sm bg-slate-50/60 cursor-pointer transition-all ${
          open
            ? 'bg-white border-indigo-500 ring-2 ring-indigo-500/20'
            : 'border-slate-200 hover:bg-white'
        }`}
      >
        {open ? (
          <div className="flex items-center gap-1.5 flex-1 min-w-0">
            <Search className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
            <input
              type="text"
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && filteredOptions.length > 0) {
                  e.preventDefault();
                  handleSelect(filteredOptions[0].value);
                } else if (e.key === 'Escape') {
                  setOpen(false);
                }
              }}
              placeholder={selectedOption ? selectedOption.label : placeholder}
              className="w-full bg-transparent text-xs sm:text-sm text-slate-800 focus:outline-none"
            />
          </div>
        ) : (
          <span
            className={`truncate ${
              selectedOption ? 'font-semibold text-indigo-700' : 'text-slate-600'
            }`}
          >
            {selectedOption ? selectedOption.label : placeholder}
          </span>
        )}

        <div className="flex items-center gap-1 shrink-0 ml-1">
          {value && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleSelect('');
              }}
              className="p-0.5 rounded-md text-slate-400 hover:text-rose-600 hover:bg-rose-50"
              title="Seçimi Temizle"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
          <ChevronDown
            className={`w-4 h-4 text-slate-400 transition-transform ${
              open ? 'rotate-180 text-indigo-600' : ''
            }`}
          />
        </div>
      </div>

      {/* Dropdown List */}
      {open && (
        <div className="absolute left-0 right-0 mt-1.5 bg-white rounded-xl border border-slate-200 shadow-xl z-40 max-h-56 overflow-y-auto py-1">
          <button
            type="button"
            onClick={() => handleSelect('')}
            className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between hover:bg-slate-50 transition-colors ${
              !value ? 'font-bold text-indigo-600 bg-indigo-50/50' : 'text-slate-600'
            }`}
          >
            <span>Tümü</span>
            {!value && <Check className="w-3.5 h-3.5 text-indigo-600" />}
          </button>

          {filteredOptions.length === 0 ? (
            <div className="px-3 py-3 text-xs text-slate-400 text-center">
              "{query}" ile eşleşen kayıt bulunamadı.
            </div>
          ) : (
            filteredOptions.map((opt) => {
              const isSelected = opt.value === value;
              return (
                <button
                  key={`${opt.value}-${opt.label}`}
                  type="button"
                  onClick={() => handleSelect(opt.value)}
                  className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between hover:bg-indigo-50/70 transition-colors ${
                    isSelected
                      ? 'font-bold text-indigo-700 bg-indigo-50'
                      : 'text-slate-700'
                  }`}
                >
                  <span className="truncate">{opt.label}</span>
                  {isSelected && <Check className="w-3.5 h-3.5 text-indigo-600 shrink-0" />}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
