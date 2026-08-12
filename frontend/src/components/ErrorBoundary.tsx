import { Component, type ReactNode } from "react"

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error) {
    console.error("Error boundary caught:", error)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[#0A0A0A] p-4 text-sm text-[#A1A1AA]">
          <div className="max-w-sm rounded-lg border border-[#2A2A2A] bg-[#111111] p-8 text-center">
            <p className="mb-6 text-white">Something went wrong rendering this page.</p>
            <button
              onClick={() => {
                this.setState({ error: null })
                window.location.assign("/")
              }}
              className="rounded-md border border-[#333] px-4 py-2 text-white transition-colors hover:bg-[#1A1A1A]"
            >
              Reload
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
