import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CreateCycleComponent } from './create-cycle.component';

describe('CreateCycleComponent', () => {
  let component: CreateCycleComponent;
  let fixture: ComponentFixture<CreateCycleComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ CreateCycleComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CreateCycleComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
