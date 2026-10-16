import { shallowRef } from 'vue'
import { api, type User } from '../api'
import { can, canVisit } from '../features/access/model'

// Always hydrate from the server before entering protected routes.
export const authUser = shallowRef<User | null>(null)
export const currentUser = authUser
export const hasPermission = (permission: string) => can(authUser.value, permission)
export const isSuperuser = () => Boolean(authUser.value?.is_superuser)
export const canAccess = (path: string) => canVisit(authUser.value, path)

export async function refreshAuth() {
  const { data } = await api.get<User>('/auth/me/')
  authUser.value = data
  localStorage.setItem('confighub_user', JSON.stringify(data))
  return data
}
