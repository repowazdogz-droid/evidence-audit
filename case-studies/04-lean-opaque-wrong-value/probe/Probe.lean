-- Does an `opaque` constant appear in `#print axioms`?
opaque mySize (T : Type) : Nat

def sizeOf' (T : Type) : Option Nat := some (mySize T)

theorem sizeOf'_total (T : Type) : ∃ n, sizeOf' T = some n := ⟨_, rfl⟩

-- Same theorem shape, but with a PINNED value instead of an opaque one.
class Sized (T : Type) where size : Nat
def sizeOf2 (T : Type) [inst : Sized T] : Option Nat := some inst.size
theorem sizeOf2_total (T : Type) [Sized T] : ∃ n, sizeOf2 T = some n := ⟨_, rfl⟩

#print axioms sizeOf'_total
#print axioms sizeOf2_total
