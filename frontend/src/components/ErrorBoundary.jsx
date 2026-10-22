import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Bileşen hatası yakalandı:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-[300px] flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-white rounded-2xl border border-rose-200 shadow-xl p-6 text-center space-y-4">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-rose-100 text-rose-600 mb-1">
              <AlertTriangle className="w-7 h-7" />
            </div>
            <h2 className="text-lg font-bold text-slate-900">
              Arayüz Yüklenirken Bir Hata Oluştu
            </h2>
            <p className="text-xs text-slate-600 bg-rose-50 p-3 rounded-xl border border-rose-100 font-mono text-left break-words">
              {this.state.error?.message || 'Bilinmeyen bir hata oluştu.'}
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className="inline-flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold shadow-xs transition-colors cursor-pointer"
            >
              <RefreshCw className="w-4 h-4" />
              Sayfayı Yenile
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

