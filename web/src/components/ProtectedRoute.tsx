import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { UserRole } from "../api/types";

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: UserRole[];
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, allowedRoles }) => {
  const { token, role } = useAuth();
  const location = useLocation();

  if (!token) {
    return <Navigate to="/start" state={{ from: location }} replace />;
  }

  if (allowedRoles && !allowedRoles.includes(role) && role !== "ops_admin") {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};
