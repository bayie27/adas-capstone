import { useState } from "react"
import SearchLineIcon from "remixicon-react/SearchLineIcon"
import AddLineIcon from "remixicon-react/AddLineIcon"
import PencilLineIcon from "remixicon-react/PencilLineIcon"
import Key2LineIcon from "remixicon-react/Key2LineIcon"
import DeleteBinLineIcon from "remixicon-react/DeleteBinLineIcon"
import UserAddLineIcon from "remixicon-react/UserAddLineIcon"
import LockLineIcon from "remixicon-react/LockLineIcon"
import AlertLineIcon from "remixicon-react/AlertLineIcon"
import EyeOffLineIcon from "remixicon-react/EyeOffLineIcon"
import { Modal } from "@/components/Modal"

interface User {
  id: number
  firstName: string
  lastName: string
  fullName: string
  username: string
  role: string
  lastLogin: string
}

const mockUsers: User[] = [
  { id: 1, firstName: "Juan", lastName: "De La Cruz", fullName: "Juan De La Cruz", username: "jdelacruz", role: "Administrator", lastLogin: "Just now" },
  { id: 2, firstName: "Jose", lastName: "Del Pilar", fullName: "Jose Del Pilar", username: "jdelpilar", role: "Operator", lastLogin: "Last 8 hrs ago" },
  { id: 3, firstName: "Juan", lastName: "De La Cruz", fullName: "Juan De La Cruz", username: "jdelacruz", role: "Administrator", lastLogin: "Last 16 hrs ago" },
]

export default function Users() {
  const [isAddOpen, setIsAddOpen] = useState(false)
  const [isEditOpen, setIsEditOpen] = useState(false)
  const [isPasswordOpen, setIsPasswordOpen] = useState(false)
  const [isDeleteOpen, setIsDeleteOpen] = useState(false)
  const [selectedUser, setSelectedUser] = useState<User | null>(null)

  const openEdit = (user: User) => {
    setSelectedUser(user)
    setIsEditOpen(true)
  }

  const openPassword = (user: User) => {
    setSelectedUser(user)
    setIsPasswordOpen(true)
  }

  const openDelete = (user: User) => {
    setSelectedUser(user)
    setIsDeleteOpen(true)
  }

  return (
    <div className="p-8 max-w-[1400px] mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-white mb-0.5">User Management</h1>
        <p className="text-[#737373] text-xs">Manage user accounts & system access roles</p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div className="relative">
          <SearchLineIcon size={14} className="text-[#555] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search..."
            className="bg-[#141414] border border-[#2A2A2A] rounded-md text-xs text-white pl-8 pr-4 py-1.5 w-64 focus:outline-none focus:border-[#52525B]"
          />
        </div>
        <button
          onClick={() => setIsAddOpen(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-white text-black font-semibold rounded-md text-xs hover:bg-gray-100 transition-colors"
        >
          <AddLineIcon size={14} />
          Add User
        </button>
      </div>

      <div className="bg-[#111111] border border-[#2A2A2A] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[#2A2A2A] text-[#737373] bg-[#141414]">
                <th className="px-6 py-4 font-medium text-xs">Full Name</th>
                <th className="px-6 py-4 font-medium text-xs">Username</th>
                <th className="px-6 py-4 font-medium text-xs">Role</th>
                <th className="px-6 py-4 font-medium text-xs">Last Login</th>
                <th className="px-6 py-4 font-medium text-xs text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#2A2A2A]">
              {mockUsers.map((user) => (
                <tr key={user.id} className="text-[#D4D4D4] hover:bg-[#1A1A1A] transition-colors">
                  <td className="px-6 py-4 text-xs font-medium">{user.fullName}</td>
                  <td className="px-6 py-4 text-xs">{user.username}</td>
                  <td className="px-6 py-4 text-xs">{user.role}</td>
                  <td className="px-6 py-4 text-xs">{user.lastLogin}</td>
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-end gap-1.5">
                      <button
                        onClick={() => openEdit(user)}
                        className="p-1.5 text-[#737373] hover:text-white transition-colors hover:bg-[#252525] rounded"
                      >
                        <PencilLineIcon size={14} />
                      </button>
                      <button
                        onClick={() => openPassword(user)}
                        className="p-1.5 text-[#737373] hover:text-white transition-colors hover:bg-[#252525] rounded"
                      >
                        <Key2LineIcon size={14} />
                      </button>
                      <button
                        onClick={() => openDelete(user)}
                        className="p-1.5 text-[#737373] hover:text-white transition-colors hover:bg-[#252525] rounded"
                      >
                        <DeleteBinLineIcon size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Modal
        isOpen={isAddOpen}
        onClose={() => setIsAddOpen(false)}
        title="Add User"
        subtitle="Create a new user & assign an access role"
        icon={<div className="w-10 h-10 rounded-full border border-[#333] flex items-center justify-center bg-transparent"><UserAddLineIcon size={20} className="text-white" /></div>}
      >
        <div className="flex flex-col gap-6 mt-4">
          <div className="grid grid-cols-[100px_1fr] gap-4">
            <div className="text-xs font-semibold text-[#E4E4E7] pt-1">User</div>
            <div className="space-y-4">
              <div className="mb-2">
                <label className="block text-[11px] font-semibold text-[#E4E4E7] mb-2">Role</label>
                <div className="flex items-center gap-8">
                  <label className="flex items-center gap-2 text-xs text-[#D4D4D4] cursor-pointer">
                    <input type="radio" name="role" className="accent-white" defaultChecked /> Administrator
                  </label>
                  <label className="flex items-center gap-2 text-xs text-[#D4D4D4] cursor-pointer">
                    <input type="radio" name="role" className="accent-white" /> Operator
                  </label>
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-[#E4E4E7] mb-2">First Name</label>
                <input type="text" placeholder="John" className="w-full bg-[#141414] border border-[#2A2A2A] rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-[#555] placeholder-[#555]" />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-[#E4E4E7] mb-2">Last Name</label>
                <input type="text" placeholder="Doe" className="w-full bg-[#141414] border border-[#2A2A2A] rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-[#555] placeholder-[#555]" />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-[#E4E4E7] mb-2">Username</label>
                <input type="text" placeholder="jdoe" className="w-full bg-[#141414] border border-[#2A2A2A] rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-[#555] placeholder-[#555]" />
              </div>
            </div>
          </div>

          <div className="h-px w-full bg-[#2A2A2A]" />

          <div className="grid grid-cols-[100px_1fr] gap-4">
            <div className="text-xs font-semibold text-[#E4E4E7] pt-1">Enter Password</div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[11px] font-semibold text-[#E4E4E7] mb-2">Password</label>
                <div className="relative">
                  <input type="password" placeholder="••••••••" className="w-full bg-[#141414] border border-[#2A2A2A] rounded-md px-3 py-2 pr-10 text-sm text-white focus:outline-none focus:border-[#555] placeholder-[#555]" />
                  <button className="absolute right-3 top-1/2 -translate-y-1/2 text-[#555] hover:text-white transition-colors">
                    <EyeOffLineIcon size={14} />
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-[#E4E4E7] mb-2">Confirm Password</label>
                <div className="relative">
                  <input type="password" placeholder="••••••••" className="w-full bg-[#141414] border border-[#2A2A2A] rounded-md px-3 py-2 pr-10 text-sm text-white focus:outline-none focus:border-[#555] placeholder-[#555]" />
                  <button className="absolute right-3 top-1/2 -translate-y-1/2 text-[#555] hover:text-white transition-colors">
                    <EyeOffLineIcon size={14} />
                  </button>
                </div>
              </div>
              <div className="col-span-2 text-[10px] text-[#737373] mt-1">
                Must be at least 8 characters long and contain at least 1 number.
              </div>
            </div>
          </div>

          <div className="h-px w-full bg-[#2A2A2A]" />

          <div className="flex items-center justify-end gap-3">
            <button onClick={() => setIsAddOpen(false)} className="px-4 py-2 border border-[#333] rounded-md text-xs font-medium text-[#E4E4E7] hover:text-white transition-colors bg-transparent">
              Cancel
            </button>
            <button className="px-4 py-2 bg-white text-black rounded-md text-xs font-medium hover:bg-gray-100 transition-colors">
              Save Changes
            </button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={isEditOpen}
        onClose={() => setIsEditOpen(false)}
        title="Edit User"
        subtitle="Update the user's account details and access role"
        icon={<div className="w-10 h-10 rounded-full border border-[#333] flex items-center justify-center bg-transparent"><PencilLineIcon size={20} className="text-white" /></div>}
      >
        <div className="flex flex-col gap-6 mt-4">
          <div className="grid grid-cols-[100px_1fr] gap-4">
            <div className="text-xs font-semibold text-[#E4E4E7] pt-1">User</div>
            <div className="space-y-4">
              <div className="mb-2">
                <label className="block text-[11px] font-semibold text-[#E4E4E7] mb-2">Role</label>
                <div className="flex items-center gap-8">
                  <label className="flex items-center gap-2 text-xs text-[#D4D4D4] cursor-pointer">
                    <input type="radio" name="editRole" className="accent-white" defaultChecked={selectedUser?.role === "Administrator"} /> Administrator
                  </label>
                  <label className="flex items-center gap-2 text-xs text-[#D4D4D4] cursor-pointer">
                    <input type="radio" name="editRole" className="accent-white" defaultChecked={selectedUser?.role === "Operator"} /> Operator
                  </label>
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-[#E4E4E7] mb-2">First Name</label>
                <input type="text" defaultValue={selectedUser?.firstName} className="w-full bg-[#141414] border border-[#2A2A2A] rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-[#555]" />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-[#E4E4E7] mb-2">Last Name</label>
                <input type="text" defaultValue={selectedUser?.lastName} className="w-full bg-[#141414] border border-[#2A2A2A] rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-[#555]" />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-[#E4E4E7] mb-2">Username</label>
                <input type="text" defaultValue={selectedUser?.username} className="w-full bg-[#141414] border border-[#2A2A2A] rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-[#555]" />
              </div>
            </div>
          </div>

          <div className="h-px w-full bg-[#2A2A2A]" />

          <div className="flex items-center justify-between">
            <div className="text-[10px] text-[#71717A] space-y-1">
              <div>Date Added: 2025-03-12</div>
              <div>Last Changes: -</div>
            </div>
            <div className="flex items-center gap-3">
              <button onClick={() => setIsEditOpen(false)} className="px-4 py-2 border border-[#333] rounded-md text-xs font-medium text-[#E4E4E7] hover:text-white transition-colors bg-transparent">
                Cancel
              </button>
              <button className="px-4 py-2 bg-white text-black rounded-md text-xs font-medium hover:bg-gray-100 transition-colors">
                Save Changes
              </button>
            </div>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={isPasswordOpen}
        onClose={() => setIsPasswordOpen(false)}
        title="Change Password"
        subtitle="Update a user's password"
        icon={<div className="w-10 h-10 rounded-full border border-[#333] flex items-center justify-center bg-transparent"><LockLineIcon size={20} className="text-white" /></div>}
      >
        <div className="flex flex-col gap-6 mt-4">
          <div className="h-px w-full bg-[#2A2A2A]" />
          <div className="space-y-4">
            <p className="text-xs text-[#A1A1AA] mb-4">Changing {selectedUser?.fullName}'s account password...</p>
            <div>
              <label className="block text-[11px] font-semibold text-[#E4E4E7] mb-2">New Password</label>
              <div className="relative">
                <input type="password" placeholder="••••••••" className="w-full bg-[#141414] border border-[#2A2A2A] rounded-md px-3 py-2 pr-10 text-sm text-white focus:outline-none focus:border-[#555] placeholder-[#555]" />
                <button className="absolute right-3 top-1/2 -translate-y-1/2 text-[#555] hover:text-white transition-colors">
                  <EyeOffLineIcon size={14} />
                </button>
              </div>
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-[#E4E4E7] mb-2">Confirm New Password</label>
              <div className="relative">
                <input type="password" placeholder="••••••••" className="w-full bg-[#141414] border border-[#2A2A2A] rounded-md px-3 py-2 pr-10 text-sm text-white focus:outline-none focus:border-[#555] placeholder-[#555]" />
                <button className="absolute right-3 top-1/2 -translate-y-1/2 text-[#555] hover:text-white transition-colors">
                  <EyeOffLineIcon size={14} />
                </button>
              </div>
            </div>
            <div className="text-[10px] text-[#737373] mt-2 mb-2">
              Must be at least 8 characters long and contain at least 1 number.
            </div>
          </div>

          <div className="h-px w-full bg-[#2A2A2A]" />

          <div className="flex items-center justify-between">
            <div className="text-[10px] text-[#71717A]">
              <div>Last Changes: 2025-03-12</div>
            </div>
            <div className="flex items-center gap-3">
              <button onClick={() => setIsPasswordOpen(false)} className="px-4 py-2 border border-[#333] rounded-md text-xs font-medium text-[#E4E4E7] hover:text-white transition-colors bg-transparent">
                Cancel
              </button>
              <button className="px-4 py-2 bg-white text-black rounded-md text-xs font-medium hover:bg-gray-100 transition-colors">
                Save Changes
              </button>
            </div>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={isDeleteOpen}
        onClose={() => setIsDeleteOpen(false)}
        hideClose
      >
        <div className="flex flex-col items-center pt-6 text-center">
          <AlertLineIcon size={36} className="text-[#ef4444] mb-4" />
          <h3 className="text-[15px] font-bold text-white mb-2">Are you absolutely sure?</h3>
          <p className="text-[11px] text-[#A1A1AA] leading-relaxed mb-6 px-4">
            This action cannot be undone. This will permanently delete account "{selectedUser?.fullName}" and remove the data from the server.
          </p>
          <div className="flex items-center justify-end gap-3 w-full">
            <button onClick={() => setIsDeleteOpen(false)} className="px-4 py-2 border border-[#333] rounded-md text-xs font-semibold text-white hover:bg-[#1A1A1A] transition-colors bg-transparent">
              Cancel
            </button>
            <button className="px-4 py-2 bg-white text-black rounded-md text-xs font-semibold hover:bg-gray-100 transition-colors">
              Continue
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
