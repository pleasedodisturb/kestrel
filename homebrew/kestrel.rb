class Kestrel < Formula
  include Language::Python::Virtualenv

  desc "AI-powered job search platform — self-hosted, open-source, privacy-first"
  homepage "https://github.com/pleasedodisturb/kestrel"
  url "https://files.pythonhosted.org/packages/source/k/kestrel-app/kestrel_app-0.1.0.tar.gz"
  sha256 "PLACEHOLDER" # TODO: update with actual sha256 once published to PyPI
  license "MIT"
  head "https://github.com/pleasedodisturb/kestrel.git", branch: "main"

  depends_on "python@3.13"

  def install
    virtualenv_install_with_resources
  end

  def caveats
    <<~EOS
      To start Kestrel:
        kestrel start

      Your data is stored in ~/.kestrel/
      Your browser will open automatically at http://localhost:8100

      Kestrel runs in Demo Mode by default (free, offline).
      To enable real AI scoring, see:
        https://github.com/pleasedodisturb/kestrel#add-real-ai-optional
    EOS
  end

  test do
    assert_match "Career OS", shell_output("#{bin}/kestrel --help")
  end
end
