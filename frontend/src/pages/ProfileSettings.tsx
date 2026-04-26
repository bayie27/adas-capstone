export default function ProfileSettings() {
  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-white mb-1">My Profile</h1>
        <p className="text-[#A1A1AA] text-sm">Manage your personal information and preferences.</p>
      </div>

      <div className="bg-[#111111] border border-[#2A2A2A] rounded-xl p-8">
        <div className="flex items-center gap-6 mb-8">
          <div className="w-24 h-24 bg-[#18181B] border border-[#27272A] rounded-full flex items-center justify-center text-3xl font-bold text-white">
            JD
          </div>
          <div>
            <h2 className="text-xl font-semibold text-white">Juan De La Cruz</h2>
            <p className="text-[#A1A1AA]">jdelacruz (Operator)</p>
          </div>
        </div>

        <div className="space-y-6 max-w-sm">
          <div>
            <label className="block text-sm font-medium text-[#E4E4E7] mb-1.5">First Name</label>
            <input type="text" defaultValue="Juan" className="w-full bg-[#141414] border border-[#333] rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-[#555]" disabled />
          </div>
          <div>
            <label className="block text-sm font-medium text-[#E4E4E7] mb-1.5">Last Name</label>
            <input type="text" defaultValue="De La Cruz" className="w-full bg-[#141414] border border-[#333] rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-[#555]" disabled />
          </div>
          <button className="px-4 py-2 bg-white text-black rounded-md text-sm font-medium hover:bg-gray-100 transition-colors">
            Change Password
          </button>
        </div>
      </div>
    </div>
  )
}
