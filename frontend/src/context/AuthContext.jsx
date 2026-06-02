import React, { createContext, useContext, useState, useEffect } from 'react';
import client from '../api/client';

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem('token');
      if (token) {
        try {
          const response = await client.get('/users/me');
          setCurrentUser(response.data);
        } catch (error) {
          console.error("Failed to fetch user, token might be invalid", error);
          localStorage.removeItem('token');
        }
      }
      setLoading(false);
    };

    initAuth();
  }, []);

  const login = async (username, password) => {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const response = await client.post('/auth/token', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });

    const { access_token } = response.data;
    localStorage.setItem('token', access_token);
    
    // Fetch user details
    const userResponse = await client.get('/users/me');
    setCurrentUser(userResponse.data);
  };

  const register = async (username, email, password) => {
    await client.post('/auth/register', {
      username,
      email,
      password,
      role: 'Reviewer',
      active: true,
    });
    // Automatically log in after registration
    await login(username, password);
  };

  const logout = () => {
    localStorage.removeItem('token');
    setCurrentUser(null);
    window.location.href = '/login';
  };

  const value = {
    currentUser,
    loading,
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{!loading && children}</AuthContext.Provider>;
};
