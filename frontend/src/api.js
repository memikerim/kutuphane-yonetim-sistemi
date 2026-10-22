const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export function getToken() {
  return localStorage.getItem('library_token');
}

export function setToken(token) {
  if (token) {
    localStorage.setItem('library_token', token);
  } else {
    localStorage.removeItem('library_token');
  }
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
    });
  } catch (err) {
    throw new Error('Sunucuya bağlanılamadı. Backend servisinin (port 8000) çalıştığından emin olun.');
  }

  if (response.status === 204) {
    return null;
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    let errorMessage = 'İşlem sırasında bir hata oluştu.';
    if (data && data.detail) {
      if (typeof data.detail === 'string') {
        errorMessage = data.detail;
      } else if (Array.isArray(data.detail)) {
        errorMessage = data.detail
          .map((item) => {
            const field = item.loc ? item.loc[item.loc.length - 1] : '';
            return field ? `${field}: ${item.msg}` : item.msg;
          })
          .join(' | ');
      }
    }
    const error = new Error(errorMessage);
    error.status = response.status;
    throw error;
  }

  return data;
}

export const api = {
  // Auth
  login: (credentials) =>
    request('/auth/login', { method: 'POST', body: JSON.stringify(credentials) }),
  register: (userData) =>
    request('/auth/register', { method: 'POST', body: JSON.stringify(userData) }),
  getMe: () => request('/auth/me'),

  // Books
  getBooks: (params = {}) => {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        searchParams.append(key, val);
      }
    });
    const qs = searchParams.toString();
    return request(`/books${qs ? `?${qs}` : ''}`);
  },
  getBook: (id) => request(`/books/${id}`),
  createBook: (data) =>
    request('/books', { method: 'POST', body: JSON.stringify(data) }),
  updateBook: (id, data) =>
    request(`/books/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteBook: (id) => request(`/books/${id}`, { method: 'DELETE' }),

  // Authors
  getAuthors: () => request('/authors'),
  createAuthor: (data) =>
    request('/authors', { method: 'POST', body: JSON.stringify(data) }),
  updateAuthor: (id, data) =>
    request(`/authors/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteAuthor: (id) => request(`/authors/${id}`, { method: 'DELETE' }),

  // Categories
  getCategories: () => request('/categories'),
  createCategory: (data) =>
    request('/categories', { method: 'POST', body: JSON.stringify(data) }),
  updateCategory: (id, data) =>
    request(`/categories/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteCategory: (id) => request(`/categories/${id}`, { method: 'DELETE' }),

  // Publishers
  getPublishers: () => request('/publishers'),
  createPublisher: (data) =>
    request('/publishers', { method: 'POST', body: JSON.stringify(data) }),
  updatePublisher: (id, data) =>
    request(`/publishers/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deletePublisher: (id) => request(`/publishers/${id}`, { method: 'DELETE' }),

  // Borrowings
  getMyBorrowings: () => request('/borrowings'),
  borrowBook: (data) =>
    request('/borrowings', { method: 'POST', body: JSON.stringify(data) }),
  returnBook: (id) =>
    request(`/borrowings/${id}/return`, { method: 'PATCH' }),
  payPenalty: (id) =>
    request(`/borrowings/${id}/pay-penalty`, { method: 'POST' }),

  // Admin Borrowings & Overdue Simulation
  getAdminBorrowings: () => request('/admin/borrowings'),
  simulateOverdue: (id) =>
    request(`/admin/borrowings/${id}/simulate-overdue`, { method: 'PATCH' }),


  // Reservations
  getMyReservations: () => request('/reservations'),
  createReservation: (data) =>
    request('/reservations', { method: 'POST', body: JSON.stringify(data) }),
  cancelReservation: (id) =>
    request(`/reservations/${id}`, { method: 'DELETE' }),


  // Reviews
  getReviews: (bookId) =>
    request(`/reviews${bookId ? `?book_id=${bookId}` : ''}`),
  createReview: (data) =>
    request('/reviews', { method: 'POST', body: JSON.stringify(data) }),
  deleteReview: (id) =>
    request(`/reviews/${id}`, { method: 'DELETE' }),
};

