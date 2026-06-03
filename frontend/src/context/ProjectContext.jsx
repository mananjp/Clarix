import React, { createContext, useContext, useState, useEffect } from 'react';
import client from '../api/client';
import { useAuth } from './AuthContext';

const ProjectContext = createContext();

export const useProjects = () => useContext(ProjectContext);

export const ProjectProvider = ({ children }) => {
  const { currentUser } = useAuth();
  const [projects, setProjects] = useState([]);
  const [isLoadingProjects, setIsLoadingProjects] = useState(true);

  const fetchProjects = async () => {
    setIsLoadingProjects(true);
    try {
      const response = await client.get('/projects');
      setProjects(response.data);
    } catch (error) {
      console.error("Failed to load projects", error);
    } finally {
      setIsLoadingProjects(false);
    }
  };

  // Only fetch if a user is logged in
  useEffect(() => {
    if (currentUser) {
      fetchProjects();
    } else {
      setProjects([]);
      setIsLoadingProjects(false);
    }
  }, [currentUser]);

  const value = {
    projects,
    isLoadingProjects,
    fetchProjects
  };

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
};
